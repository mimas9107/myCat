import logging
import os
import time

from PySide6.QtCore import QThread, Signal

from . import device_store
from .config_loader import load_config
from .core.asr_pipeline import ASRPipeline
from .core.audio_stream import AudioStreamManager
from .core.intent_parser import parse_text_to_intent
from .core.vad_filter import EnergyVAD, VoiceVAD
from .core.wake_word import WakeWordEngine

logger = logging.getLogger(__name__)


class VoiceWorker(QThread):
    """QThread Worker that coordinates core voice components and emits Qt signals."""

    ASR_LOADING = "ASR_LOADING"
    ASR_READY = "ASR_READY"
    ASR_UNLOADED = "ASR_UNLOADED"

    status_changed_signal = Signal(
        str
    )
    intent_detected_signal = Signal(dict)
    vad_energy_signal = Signal(float)
    asr_status_signal = Signal(str)

    def __init__(self, config_path=None, parent=None):
        super().__init__(parent)
        self.config = load_config(config_path) if config_path else load_config()
        self._is_running = False

        audio_cfg = self.config.get("audio", {})
        vad_cfg = self.config.get("vad", {})
        ww_cfg = self.config.get("wake_word", {})
        asr_cfg = self.config.get("asr", {})

        saved_device = device_store.load_saved_device_index()
        device_index = saved_device if saved_device is not None else audio_cfg.get("device_index")

        # MYCAT_AUDIO_WAV swaps the mic for a WAV file (real pipeline, fake source).
        # Used by the automated tests on machines without audio hardware.
        wav_source = os.environ.get("MYCAT_AUDIO_WAV")
        if wav_source:
            from .core.audio_stream import WavAudioStreamManager
            self.audio_stream = WavAudioStreamManager(
                wav_source,
                sample_rate=audio_cfg.get("sample_rate", 16000),
                chunk_duration_ms=audio_cfg.get("chunk_duration_ms", 100),
                buffer_seconds=audio_cfg.get("buffer_seconds", 3),
                start_delayed=True,
            )
        else:
            self.audio_stream = AudioStreamManager(
                sample_rate=audio_cfg.get("sample_rate", 16000),
                chunk_duration_ms=audio_cfg.get("chunk_duration_ms", 100),
                buffer_seconds=audio_cfg.get("buffer_seconds", 3),
                device_index=device_index,
            )
        self.vad_threshold = vad_cfg.get("threshold", 3873.0)
        self.vad = EnergyVAD(threshold=self.vad_threshold)

        # Layer 1 voice filter (PLAN-3c): absent/disabled section = pure L0,
        # byte-for-byte legacy behavior.
        voice_cfg = vad_cfg.get("voice") or {}
        self.voice_vad = None
        if voice_cfg.get("enabled", False):
            self.voice_vad = VoiceVAD(
                sample_rate=audio_cfg.get("sample_rate", 16000),
                freq_min=voice_cfg.get("freq_min", 300),
                freq_max=voice_cfg.get("freq_max", 3400),
                snr_on=voice_cfg.get("snr_on", 2.25),
                snr_off=voice_cfg.get("snr_off", 1.5),
                min_speech_ms=voice_cfg.get("min_speech_ms", 200),
                release_ms=voice_cfg.get("release_ms", 300),
                floor_alpha=voice_cfg.get("floor_alpha", 0.01),
                smooth_alpha=voice_cfg.get("smooth_alpha", 0.3),
            )
        self._voice_vad_active = self.voice_vad is not None

        # Retrigger suppression (PLAN-3d): lockout + L1 release wait + cap
        self._retrigger_lockout_ms = vad_cfg.get("retrigger_lockout_ms", 1500)
        self._rearm_max_wait_ms = vad_cfg.get("rearm_max_wait_ms", 10000)
        self._rearm_lockout_until = 0.0
        self._last_trigger_time = 0.0
        self._rearming = False

        self._ww_enabled = ww_cfg.get("enabled", False)
        self.wake_word = None
        if self._ww_enabled:
            self.wake_word = WakeWordEngine(
                model_path=ww_cfg.get("model_path", "models/impulse_model.eim"),
                threshold=ww_cfg.get("threshold", 0.8),
            )

        self.asr = ASRPipeline(
            model_size=asr_cfg.get("model_size", "base"),
            device=asr_cfg.get("device", "cpu"),
            compute_type=asr_cfg.get("compute_type", "int8"),
            language=asr_cfg.get("language", "en"),
        )

        self.drop_after_warmup_sec = asr_cfg.get("drop_after_warmup_sec", 5.0)
        self._warmup_start_time = None
        self._asr_status = self.ASR_UNLOADED

    def run(self):
        """Main loop executed in background QThread."""
        self._is_running = True
        try:
            self.audio_stream.start()
        except Exception as e:
            logger.error("Failed to start AudioStreamManager: %s", e)

        self.status_changed_signal.emit("LISTENING")
        logger.info("Started | device=%s | VAD threshold=%.0f | WakeWord=%s | VoiceVAD=%s",
                    self.audio_stream.device_index, self.vad_threshold,
                    "on" if self._ww_enabled else "off",
                    "on" if self._voice_vad_active else "off")

        self.asr.load()
        self._warmup_start_time = time.time()
        self._asr_status = self.ASR_READY
        self.asr_status_signal.emit(self._asr_status)

        # Gated WAV sources (tests) start playing only once the consumer loop
        # is about to poll, mirroring live-mic "capture while listening".
        resume = getattr(self.audio_stream, "resume", None)
        if callable(resume):
            resume()

        rms_log_throttle = 0.0
        while self._is_running:
            time.sleep(0.1)
            now = time.time()

            audio_buffer = self.audio_stream.get_buffered_audio()
            if len(audio_buffer) == 0:
                continue

            # RMS logging throttle (previously vad_cooldown, misnamed; only throttles [vad] RMS log)
            if now - rms_log_throttle > 2.0:
                recent_chunk = self.audio_stream.get_recent_chunk(0.1)
                if len(recent_chunk) > 0:
                    energy = self.vad.get_energy(recent_chunk)
                    self.vad_energy_signal.emit(energy)
                    logger.info("[vad] RMS=%.0f (threshold=%.0f)", energy, self.vad_threshold)
                rms_log_throttle = now

            # Re-arm gate: skip ASR trigger while re-arming, but keep feeding L1
            # so its adaptive floor and speaking state stay current.
            recent_chunk = self.audio_stream.get_recent_chunk(0.1)
            if len(recent_chunk) == 0:
                continue

            if self._rearming:
                # Feed L1 during re-arm so it can detect speech release
                if self._voice_vad_active:
                    try:
                        self.voice_vad.is_speech(recent_chunk)
                    except Exception:
                        pass

                lockout_expired = now * 1000 >= self._rearm_lockout_until
                l1_released = True
                if self._voice_vad_active:
                    l1_released = not self.voice_vad.speaking
                cap_expired = (now * 1000 - self._last_trigger_time) >= self._rearm_max_wait_ms

                if lockout_expired and (l1_released or cap_expired):
                    self._rearming = False
                    logger.info("[rearm] armed again (lockout=%s l1_released=%s cap=%s)",
                                lockout_expired, l1_released, cap_expired)
                else:
                    continue  # still re-arming, skip L0 check

            # Layer 1 is fed every chunk so its adaptive floor keeps tracking
            # ambient even when Layer 0 would reject; trigger = L0 AND L1.
            voice_ok = True
            if self._voice_vad_active:
                try:
                    voice_ok = self.voice_vad.is_speech(recent_chunk)
                except Exception as e:
                    logger.warning("[voice-vad] error (%s), falling back to pure EnergyVAD", e)
                    self._voice_vad_active = False

            if not self.vad.is_speech(recent_chunk):
                continue

            if not voice_ok:
                logger.info("[voice-vad] VETO score=%.2f floor=%.0f (L0 passed)",
                            self.voice_vad.last_score, self.voice_vad.noise_floor)
                continue

            energy_now = self.vad.get_energy(recent_chunk)
            logger.info("[vad] TRIGGER! RMS=%.0f (threshold=%.0f)", energy_now, self.vad_threshold)

            if self._asr_status == self.ASR_UNLOADED:
                logger.info("[asr] Model not loaded, loading now...")
                self.asr.load()
                self._warmup_start_time = time.time()
                self._asr_status = self.ASR_READY
                self.asr_status_signal.emit(self._asr_status)

            if self._warmup_start_time and (now - self._warmup_start_time) < self.drop_after_warmup_sec:
                logger.info("[asr] Skipping transcription (warmup window: %.1fs < %.1fs)",
                            now - self._warmup_start_time, self.drop_after_warmup_sec)
                continue

            self.status_changed_signal.emit("TRANSCRIBING")

            cmd_audio = audio_buffer[-int(self.audio_stream.sample_rate * 2):]
            if len(cmd_audio) < self.audio_stream.sample_rate:
                continue

            logger.info("[asr] transcribing %.1fs audio...", len(cmd_audio) / self.audio_stream.sample_rate)
            transcription = self.asr.transcribe(cmd_audio)

            if transcription:
                logger.info("[asr] result: '%s'", transcription)
                intent = parse_text_to_intent(transcription)
                self.intent_detected_signal.emit(intent)

                if intent.get("type") == "SLEEP":
                    logger.info("[asr] SLEEP intent detected, unloading model...")
                    self.asr.unload()
                    self._asr_status = self.ASR_UNLOADED
                    self.asr_status_signal.emit(self._asr_status)

                # Retrigger suppression: clear buffer + enter re-arm
                self.audio_stream.clear_buffer()
                self._rearming = True
                self._last_trigger_time = now * 1000
                self._rearm_lockout_until = self._last_trigger_time + self._retrigger_lockout_ms
                logger.info("[rearm] entered (lockout_until=%.0f max_wait_until=%.0f)",
                            self._rearm_lockout_until, self._last_trigger_time + self._rearm_max_wait_ms)
            else:
                logger.info("[asr] returned empty text")
                # Also clear buffer on empty result to prevent same audio window
                # from re-triggering VAD on next poll (no re-arm needed).
                self.audio_stream.clear_buffer()

            self.status_changed_signal.emit("LISTENING")

    def stop(self):
        """Stops the thread safely."""
        self._is_running = False
        try:
            self.audio_stream.stop()
            if self.wake_word:
                self.wake_word.stop()
        except Exception as e:
            logger.error("Error stopping components: %s", e)
        self.wait()

    def update_device(self, device_index: int) -> bool:
        """Update audio device and restart stream. Returns True on success."""
        try:
            logger.info("Updating device to index=%d", device_index)
            self.audio_stream.stop()
            self.audio_stream.device_index = device_index
            self.audio_stream.start()
            device_store.save_device_index(device_index)
            logger.info("Device updated successfully")
            return True
        except Exception as e:
            logger.error("Failed to update device: %s", e)
            return False
