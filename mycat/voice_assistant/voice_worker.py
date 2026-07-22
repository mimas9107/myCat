import time
import numpy as np
from PySide6.QtCore import QThread, Signal

from .config_loader import load_config
from .core.audio_stream import AudioStreamManager
from .core.vad_filter import EnergyVAD
from .core.wake_word import WakeWordEngine
from .core.asr_pipeline import ASRPipeline
from .core.intent_parser import parse_text_to_intent


class VoiceWorker(QThread):
    """QThread Worker that coordinates core voice components and emits Qt signals."""

    # Signals
    status_changed_signal = Signal(
        str
    )  # e.g., "LISTENING", "WAKE_WORD_TRIGGERED", "TRANSCRIBING"
    intent_detected_signal = Signal(dict)  # e.g., {"type": "CHAT", "data": {...}}
    vad_energy_signal = Signal(float)  # [DEBUG] current audio energy level

    def __init__(self, config_path=None, parent=None):
        super().__init__(parent)
        self.config = load_config(config_path) if config_path else load_config()
        self._is_running = False

        audio_cfg = self.config.get("audio", {})
        vad_cfg = self.config.get("vad", {})
        ww_cfg = self.config.get("wake_word", {})
        asr_cfg = self.config.get("asr", {})

        self.audio_stream = AudioStreamManager(
            sample_rate=audio_cfg.get("sample_rate", 16000),
            chunk_duration_ms=audio_cfg.get("chunk_duration_ms", 100),
            buffer_seconds=audio_cfg.get("buffer_seconds", 3),
        )
        self.vad_threshold = vad_cfg.get("threshold", 50000.0)
        self.vad = EnergyVAD(threshold=self.vad_threshold)
        self.wake_word = WakeWordEngine(
            model_path=ww_cfg.get("model_path", "models/impulse_model.eim"),
            threshold=ww_cfg.get("threshold", 0.8),
        )
        self.asr = ASRPipeline(
            model_size=asr_cfg.get("model_size", "base"),
            device=asr_cfg.get("device", "cpu"),
            compute_type=asr_cfg.get("compute_type", "int8"),
        )

    def run(self):
        """Main loop executed in background QThread."""
        self._is_running = True
        try:
            self.audio_stream.start()
        except Exception as e:
            print(f"[VoiceWorker] Failed to start AudioStreamManager: {e}")

        self.status_changed_signal.emit("LISTENING")
        print(f"[VoiceWorker] Started | VAD threshold={self.vad_threshold} | WakeWord={not self.wake_word._initialized}")

        vad_cooldown = 0.0
        while self._is_running:
            time.sleep(0.1)
            audio_buffer = self.audio_stream.get_buffered_audio()
            if len(audio_buffer) == 0:
                continue

            # VAD energy logging every 2 seconds
            now = time.time()
            if now - vad_cooldown > 2.0:
                recent_chunk = (
                    audio_buffer[-self.audio_stream.chunk_size :]
                    if len(audio_buffer) >= self.audio_stream.chunk_size
                    else audio_buffer
                )
                energy = self.vad.get_energy(recent_chunk)
                self.vad_energy_signal.emit(energy)
                vad_cooldown = now

            # 1. VAD Filter
            recent_chunk = (
                audio_buffer[-self.audio_stream.chunk_size :]
                if len(audio_buffer) >= self.audio_stream.chunk_size
                else audio_buffer
            )
            if not self.vad.is_speech(recent_chunk):
                continue

            # [Path C] Bypass wake word — go straight to ASR
            print(f"[VoiceWorker] VAD TRIGGER! energy={energy:.0f} (threshold={self.vad_threshold})")
            self.status_changed_signal.emit("TRANSCRIBING")

            # Capture audio for transcription (grab 2 seconds of buffer)
            cmd_audio = audio_buffer[-int(self.audio_stream.sample_rate * 2):]
            if len(cmd_audio) < self.audio_stream.sample_rate:
                continue

            # 2. Speech Transcription
            print("[VoiceWorker] → ASR transcribing...")
            transcription = self.asr.transcribe(cmd_audio)

            # 3. Intent Parsing & Signal Dispatch
            if transcription:
                print(f"[VoiceWorker] ASR result: '{transcription}'")
                intent = parse_text_to_intent(transcription)
                self.intent_detected_signal.emit(intent)
            else:
                print("[VoiceWorker] ASR returned empty text")

            self.status_changed_signal.emit("LISTENING")
            print("[VoiceWorker] → back to LISTENING")

    def stop(self):
        """Stops the thread safely."""
        self._is_running = False
        try:
            self.audio_stream.stop()
            self.wake_word.stop()
        except Exception as e:
            print(f"[VoiceWorker] Error stopping components: {e}")
        self.wait()
