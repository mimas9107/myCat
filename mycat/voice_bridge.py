"""Single integration point for all voice features in PixelCatWindow.

Consolidates SpeechBubble, VoiceWorker/MockVoiceWorker, and
VoiceAnimationController into one bridge.  main.py keeps exactly 3
touch-points:  __init__ (start), paintEvent (apply_paint),
closeEvent (shutdown) plus two one-liners in pack_tick and intent dispatch.

Debug logging
-------------
Set env ``VOICE_BRIDGE_DEBUG=1`` to enable decoupling / callback trace
logging.  After 3 consecutive clean commits, flip to 0 (or remove).
"""

from __future__ import annotations

import logging
import os

from PySide6 import QtCore, QtGui

logger = logging.getLogger(__name__)

# ── debug toggle ──────────────────────────────────────────────
_DEBUG = os.environ.get("VOICE_BRIDGE_DEBUG", "0") == "1"

def _dbg(msg: str, *args) -> None:
    if _DEBUG:
        logger.info("[voice-bridge] " + msg, *args)


class VoiceBridge(QtCore.QObject):
    """Owns voice worker, bubble, animation; exposes minimal API to main.py."""

    def __init__(self, window, mock_voice: bool = False,
                 test_wav: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.window = window
        self._worker = None
        self._bubble = None
        self._anim = None
        self._llm_backend = None
        self._chat_thread = None

        # callbacks set by main.py for intents that need window internals
        self._sleep_callback = None
        self._reminder_callback = None

        self._init_bubble()
        self._init_worker(mock_voice, test_wav)
        self._init_animation()

    # ── init helpers ──────────────────────────────────────────

    def _init_bubble(self) -> None:
        try:
            from mycat.speech_bubble import SpeechBubble
            self._bubble = SpeechBubble()
            _dbg("SpeechBubble created")
        except Exception as exc:
            _dbg("SpeechBubble unavailable: %s", exc)
            self._bubble = None

    def _init_worker(self, mock_voice: bool, test_wav: str | None) -> None:
        try:
            if mock_voice:
                from mycat.mock_voice import MockVoiceWorker
                self._worker = MockVoiceWorker(test_wav=test_wav)
            else:
                from mycat.voice_assistant.voice_worker import VoiceWorker
                self._worker = VoiceWorker()
            self._worker.status_changed_signal.connect(self._on_status)
            self._worker.intent_detected_signal.connect(self._on_intent)
            self._worker.start()
            _dbg("Worker started (mock=%s)", mock_voice)
        except Exception as exc:
            logger.warning("Voice Assistant worker disabled or failed to start: %s", exc)
            self._worker = None

    def _init_animation(self) -> None:
        if self._worker is None:
            return
        try:
            from mycat.voice_animation import VoiceAnimationController
            self._anim = VoiceAnimationController(
                window=self.window,
                voice_worker=self._worker,
                time_fn=self.window.pack_now,
            )
            _dbg("VoiceAnimationController created")
        except Exception as exc:
            _dbg("VoiceAnimationController unavailable: %s", exc)
            self._anim = None

    # ── public API ────────────────────────────────────────────

    def start(self) -> None:
        """No-op — worker already started in __init__.  Exists for call-site clarity."""
        pass

    def shutdown(self) -> None:
        """Stop the voice worker thread.  Called from closeEvent."""
        if self._worker and self._worker.isRunning():
            _dbg("stopping worker")
            self._worker.stop()

    def apply_paint(self, painter: QtGui.QPainter,
                    x: int, y: int, cat_w: int, cat_h: int) -> None:
        """Draw overlay + bubble.  Called from paintEvent."""
        if self._anim:
            self._anim.apply_overlay(painter, x, y)
        if self._bubble:
            self._bubble.paint(painter, x, y, cat_w, cat_h)

    def should_repaint(self) -> bool:
        """True when overlay or bubble is active and needs animation frames."""
        if self._anim and self._anim.has_active_overlay:
            return True
        if self._bubble and self._bubble.is_active:
            return True
        return False

    def handle_intent(self, intent_type: str, data: dict) -> bool:
        """Handle voice intent side-effects.  Returns True if handled.

        CHAT / SET_REMINDER / SLEEP are handled here.
        Main.py only needs to call this from _on_voice_intent_detected.
        """
        _dbg("handle_intent: type=%s", intent_type)

        if intent_type == "CHAT":
            user_text = data.get("text", "")
            if user_text and self._llm_backend:
                self._voice_chat(user_text)
            else:
                _dbg("CHAT skipped: no backend or empty text")
            return True

        if intent_type == "SET_REMINDER":
            if self._reminder_callback:
                _dbg("SET_REMINDER → callback")
                self._reminder_callback()
            else:
                _dbg("SET_REMINDER → no callback registered")
            return True

        if intent_type == "SLEEP":
            if self._sleep_callback:
                _dbg("SLEEP → callback")
                self._sleep_callback()
            else:
                _dbg("SLEEP → no callback, closing window")
                self.window.close()
            return True

        return False

    def set_llm_backend(self, backend) -> None:
        self._llm_backend = backend
        _dbg("LLM backend set: %s", type(backend).__name__ if backend else None)

    def set_sleep_callback(self, fn) -> None:
        self._sleep_callback = fn
        _dbg("sleep callback registered: %s", fn)

    def set_reminder_callback(self, fn) -> None:
        self._reminder_callback = fn
        _dbg("reminder callback registered: %s", fn)

    @property
    def is_active(self) -> bool:
        """True when voice subsystem is operational."""
        return self._worker is not None

    # ── internal: status signal ───────────────────────────────

    def _on_status(self, status: str) -> None:
        logger.info("Voice Assistant status changed: %s", status)

    # ── internal: intent signal ───────────────────────────────

    def _on_intent(self, intent: dict) -> None:
        logger.info("Voice Assistant intent detected: %s", intent)
        intent_type = intent.get("type")
        data = intent.get("data", {})
        self.handle_intent(intent_type, data)

    # ── internal: voice chat via Ollama ───────────────────────

    def _voice_chat(self, user_text: str) -> None:
        """Send voice text to Ollama in a background thread, show response in bubble."""
        backend = self._llm_backend
        if not backend or not self._bubble:
            return
        if self._anim:
            self._anim.set_overlay("think", 300.0)
        self.window.update()

        class _Worker(QtCore.QObject):
            done = QtCore.Signal(str)
            error = QtCore.Signal(str)
            def run(self):
                try:
                    reply = backend.reply(
                        user_text,
                        "You are a cute cat. Reply briefly and playfully.",
                    )
                    self.done.emit(reply)
                except Exception as exc:
                    self.error.emit(str(exc))

        thread = QtCore.QThread(self)
        worker = _Worker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(lambda text: self._on_chat_done(text))
        worker.error.connect(lambda err: self._on_chat_error(err))
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        worker.deleteLater()
        thread.start()
        self._chat_thread = thread
        _dbg("voice chat thread started")

    def _on_chat_done(self, text: str) -> None:
        if self._anim:
            self._anim.clear_overlay()
        if self._bubble:
            self._bubble.show(text)
        if self._anim:
            self._anim.set_overlay("react", 0.5)
        self.window.update()

    def _on_chat_error(self, err: str) -> None:
        if self._anim:
            self._anim.clear_overlay()
        self.window.update()
        logger.warning("[voice-chat] Ollama error: %s", err)
