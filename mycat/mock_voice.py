"""Mock VoiceWorker for testing voice-driven animations without real audio.

Emits status_changed_signal / intent_detected_signal on a QTimer cycle,
simulating the wake → transcribe → intent pipeline.

Usage:
    python -m mycat --mock-voice          # auto-cycle demo
    python -m mycat --mock-voice --test-wav /path/to/file.wav  # feed WAV through real ASR→Ollama→Bubble
    python -m mycat.mock_voice            # standalone interactive menu
"""

import logging
import struct
import wave

from PySide6.QtCore import QThread, Signal, QTimer

logger = logging.getLogger(__name__)

# Auto-cycle: list of (delay_seconds, kind, value)
# delay is the gap FROM THE PREVIOUS event, not absolute time.
_AUTO_CYCLE = [
    (1.0, "status", "LISTENING"),
    (2.0, "status", "WAKE_WORD_TRIGGERED"),
    (1.5, "status", "TRANSCRIBING"),
    (2.0, "status", "LISTENING"),
]


def _load_wav_mono(path: str):
    """Load a WAV file and return (numpy_array_float32, sample_rate)."""
    import numpy as np
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
    samples = list(struct.unpack(f"<{n * ch}h", raw))
    if ch > 1:
        samples = [samples[i] for i in range(0, len(samples), ch)]
    audio = np.array(samples, dtype=np.float32)
    if sr != 16000:
        ratio = 16000 / sr
        new_len = int(len(audio) * ratio)
        audio = np.interp(
            np.linspace(0, len(audio), new_len, endpoint=False),
            np.arange(len(audio)),
            audio,
        ).astype(np.float32)
        sr = 16000
    return audio, sr


class MockVoiceWorker(QThread):
    """Drop-in replacement for VoiceWorker.  Emits signals on a timer.

    When test_wav is provided, feeds the WAV through the real ASR→Intent
    pipeline instead of the auto-cycle demo.
    """

    status_changed_signal = Signal(str)
    intent_detected_signal = Signal(dict)

    def __init__(self, parent=None, test_wav: str | None = None):
        super().__init__(parent)
        self._is_running = False
        self._cycle_index = 0
        self._test_wav = test_wav

    def run(self):
        self._is_running = True
        if self._test_wav:
            logger.info("[mock-voice] test-wav mode: %s", self._test_wav)
            self._run_test_wav()
        else:
            logger.info("[mock-voice] started — auto-cycle %d events", len(_AUTO_CYCLE))
            self._schedule_next()
            self.exec()

    def _run_test_wav(self):
        """Feed a WAV through the real ASR→Intent chain, emit signals."""
        import time
        from mycat.voice_assistant.core.asr_pipeline import ASRPipeline
        from mycat.voice_assistant.core.intent_parser import parse_text_to_intent

        audio, sr = _load_wav_mono(self._test_wav)
        logger.info("[mock-voice] loaded %d samples (%.1fs)", len(audio), len(audio) / sr)

        self.status_changed_signal.emit("TRANSCRIBING")
        asr = ASRPipeline(model_size="base", device="cpu", compute_type="int8", language="en")
        t0 = time.time()
        text = asr.transcribe(audio)
        dt = time.time() - t0
        logger.info("[mock-voice] ASR (%.1fs): '%s'", dt, text)

        intent = parse_text_to_intent(text)
        logger.info("[mock-voice] intent: %s", intent)
        self.intent_detected_signal.emit(intent)
        self.status_changed_signal.emit("LISTENING")

    def _schedule_next(self):
        """Schedule the next event using QTimer.singleShot (works reliably in QThread)."""
        if not self._is_running:
            return
        if self._cycle_index >= len(_AUTO_CYCLE):
            self._cycle_index = 0
        delay_ms = int(_AUTO_CYCLE[self._cycle_index][0] * 1000)
        QTimer.singleShot(delay_ms, self._fire)

    def _fire(self):
        """Emit the current event and schedule the next one."""
        if not self._is_running:
            return
        if self._cycle_index >= len(_AUTO_CYCLE):
            self._cycle_index = 0
        _delay, kind, value = _AUTO_CYCLE[self._cycle_index]
        self._cycle_index += 1

        if kind == "status":
            logger.info("[mock-voice] emit status=%s", value)
            self.status_changed_signal.emit(value)
        elif kind == "intent":
            logger.info("[mock-voice] emit intent=%s", value)
            self.intent_detected_signal.emit(value)

        self._schedule_next()

    # ── manual triggers ──────────────────────────────────────

    def trigger_status(self, status: str):
        logger.info("[mock-voice] manual status=%s", status)
        self.status_changed_signal.emit(status)

    def trigger_intent(self, intent: dict):
        logger.info("[mock-voice] manual intent=%s", intent)
        self.intent_detected_signal.emit(intent)

    def stop(self):
        self._is_running = False
        self.quit()
        self.wait()


def run_interactive():
    """Standalone interactive menu for manual event triggering."""
    import sys
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication(sys.argv)
    worker = MockVoiceWorker()
    worker.start()

    commands = {
        "1": ("status", "LISTENING"),
        "2": ("status", "WAKE_WORD_TRIGGERED"),
        "3": ("status", "TRANSCRIBING"),
        "4": ("intent", {"type": "CHAT", "data": {"text": "hello"}}),
        "5": ("intent", {"type": "SET_REMINDER", "data": {"message": "test"}}),
        "6": ("intent", {"type": "SLEEP", "data": {}}),
    }

    print("\n=== Mock Voice Events ===")
    print("1) LISTENING")
    print("2) WAKE_WORD_TRIGGERED")
    print("3) TRANSCRIBING")
    print("4) CHAT intent")
    print("5) SET_REMINDER intent")
    print("6) SLEEP intent")
    print("q) quit\n")

    while True:
        try:
            choice = input("event> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if choice == "q":
            break
        if choice in commands:
            kind, value = commands[choice]
            if kind == "status":
                worker.trigger_status(value)
            else:
                worker.trigger_intent(value)
        else:
            print("unknown command")

    worker.stop()


if __name__ == "__main__":
    run_interactive()
