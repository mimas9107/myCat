import logging
import time

from PySide6.QtCore import QThread, Signal

from . import device_store
from .config_loader import load_config
from .core.asr_pipeline import ASRPipeline
from .core.audio_stream import AudioStreamManager
from .core.intent_parser import parse_text_to_intent
from .core.vad_filter import EnergyVAD
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

        self.audio_stream = AudioStreamManager(
            sample_rate=audio_cfg.get("sample_rate", 16000),
            chunk_duration_ms=audio_cfg.get("chunk_duration_ms", 100),
            buffer_seconds=audio_cfg.get("buffer_seconds", 3),
            device_index=device_index,
        )
        self.vad_threshold = vad_cfg.get("threshold", 3873.0)
        self.vad = EnergyVAD(threshold=self.vad_threshold)

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
        logger.info("Started | device=%s | VAD threshold=%.0f | WakeWord=%s",
                     self.audio_stream.device_index, self.vad_threshold,
                     "on" if self._ww_enabled else "off")

        self.asr.load()
        self._warmup_start_time = time.time()
        self._asr_status = self.ASR_READY
        self.asr_status_signal.emit(self._asr_status)

        vad_cooldown = 0.0
        while self._is_running:
            time.sleep(0.1)
            audio_buffer = self.audio_stream.get_buffered_audio()
            if len(audio_buffer) == 0:
                continue

            now = time.time()
            if now - vad_cooldown > 2.0:
                recent_chunk = self.audio_stream.get_recent_chunk(0.1)
                if len(recent_chunk) > 0:
                    energy = self.vad.get_energy(recent_chunk)
                    self.vad_energy_signal.emit(energy)
                    logger.info("[vad] RMS=%.0f (threshold=%.0f)", energy, self.vad_threshold)
                vad_cooldown = now

            recent_chunk = self.audio_stream.get_recent_chunk(0.1)
            if len(recent_chunk) == 0:
                continue

            if not self.vad.is_speech(recent_chunk):
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
            else:
                logger.info("[asr] returned empty text")

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
