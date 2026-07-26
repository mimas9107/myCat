"""Single integration point for all voice features in PixelCatWindow.

Consolidates SpeechBubble, VoiceWorker/MockVoiceWorker, and
VoiceAnimationController into one bridge.  Callbacks (sleep, reminder)
are auto-wired from the window in __init__.

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

    def __init__(self, window, parent=None) -> None:
        super().__init__(parent)
        self.window = window
        self._worker = None
        self._bubble = None
        self._anim = None
        self._llm_backend = None
        self._chat_thread = None

        # callbacks for intents that need window internals
        self._sleep_callback = None
        self._reminder_callback = None

        self._init_bubble()
        self._init_worker()
        self._init_animation()
        self._auto_wire_callbacks()

    def _init_bubble(self) -> None:
        try:
            from mycat.bubble_popup import BubblePopup
            self._bubble = BubblePopup(self.window)
            _dbg("BubblePopup created")
        except Exception as exc:
            _dbg("BubblePopup unavailable: %s", exc)
            self._bubble = None

    def _init_worker(self) -> None:
        mock_voice = os.environ.get("MYCAT_MOCK_VOICE", "0") == "1"
        test_wav = os.environ.get("MYCAT_TEST_WAV")
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
            overlay_cfg = self._worker.config.get("overlay", {})
            overlay_enabled = overlay_cfg.get("enabled", True)
            idle_yawn_after = overlay_cfg.get("idle_yawn_after", 30.0)
            self._anim = VoiceAnimationController(
                window=self.window,
                voice_worker=self._worker,
                time_fn=self.window.pack_now,
                overlay_enabled=overlay_enabled,
                idle_yawn_after=float(idle_yawn_after),
            )

            # Load voice-specific char assets (think.png, listen.png, yawn.png)
            voice_pack = self._load_voice_pack()
            if voice_pack is not None:
                self._anim.set_voice_pack(voice_pack)

            _dbg("VoiceAnimationController created")
        except Exception as exc:
            _dbg("VoiceAnimationController unavailable: %s", exc)
            self._anim = None

    def _load_voice_pack(self):
        """Load VoiceCharPack if char path is known and render size available."""
        from pathlib import Path
        try:
            from mycat.voice_char_pack import VoiceCharPack
            char_name = getattr(self.window, "file_name", None)
            if char_name is None:
                return None
            char_path = Path(__file__).resolve().parent / "chars" / f"{char_name}.zip"
            if not char_path.exists():
                # Try folder
                char_path = Path(__file__).resolve().parent / "chars" / char_name
                if not char_path.is_dir():
                    return None
            cur_pixmap = getattr(self.window, "current_pixmap", None)
            if cur_pixmap is None:
                return None
            return VoiceCharPack(
                str(char_path),
                target_width=cur_pixmap.width(),
                target_height=cur_pixmap.height(),
            )
        except Exception as exc:
            _dbg("VoiceCharPack load skipped: %s", exc)
            return None

    # ── init helpers ──────────────────────────────────────────

    def _auto_wire_callbacks(self) -> None:
        self._sleep_callback = self._window_sleep_animation
        reminder_fn = getattr(self.window, 'open_reminder', None)
        if reminder_fn:
            self._reminder_callback = reminder_fn

    def _window_sleep_animation(self) -> None:
        window = self.window
        if window.char_pack is not None and (
            window.char_pack.sleep is not None or window.char_pack.sleep_in is not None
        ):
            now = window.pack_now()
            if window.char_pack.sleep_in is not None:
                window.start_clip(window.char_pack.sleep_in, "sleeping", now)
            else:
                window.base_state = "sleeping"
                window.current_pixmap = window.char_pack.sleep or window.char_pack.static
            window.update()
            logger.info("[voice-intent] SLEEP → sleep animation triggered")
        else:
            logger.info("[voice-intent] SLEEP → no CharPack sleep support, closing")
            window.close()

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
        """Draw overlay.  Bubble is a separate popup window (self-rendering)."""
        if self._anim:
            self._anim.apply_overlay(painter, x, y)

    def should_repaint(self) -> bool:
        """True when overlay is active and needs animation frames."""
        if self._anim and self._anim.has_active_overlay:
            return True
        return False

    @property
    def overlay_replaces_face(self) -> bool:
        """True when active overlay has a voice char sprite → skip drawing cat face."""
        return bool(self._anim and self._anim.overlay_replaces_face)

    def get_bubble_bounds(self, *args) -> QtCore.QRect | None:
        """Bubble is a separate popup window — no mask expansion needed."""
        return None

    def handle_intent(self, intent_type: str, data: dict) -> bool:
        """Handle voice intent side-effects.  Returns True if handled.

        CHAT / SET_REMINDER / SLEEP are handled here.
        Called from _on_intent signal handler (internal).
        """
        _EMOJI = {"CHAT": "💬", "SET_REMINDER": "⏰", "SLEEP": "😴"}
        tag = _EMOJI.get(intent_type, "🎯")
        _dbg("handle_intent: %s %s", tag, intent_type)

        if intent_type == "CHAT":
            user_text = data.get("text", "")
            if user_text and self._llm_backend:
                self._voice_chat(user_text)
            else:
                _dbg("💬 CHAT skipped: no backend or empty text")
            return True

        if intent_type == "SET_REMINDER":
            if self._reminder_callback:
                _dbg("⏰ SET_REMINDER → callback")
                self._reminder_callback()
            else:
                _dbg("⏰ SET_REMINDER → no callback registered")
            return True

        if intent_type == "SLEEP":
            if self._sleep_callback:
                _dbg("😴 SLEEP → callback")
                self._sleep_callback()
            else:
                _dbg("😴 SLEEP → no callback, closing window")
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
    def is_bubble_active(self) -> bool:
        return bool(self._bubble and self._bubble.is_active)

    @property
    def is_active(self) -> bool:
        """True when voice subsystem is operational."""
        return self._worker is not None

    # ── internal: status signal ───────────────────────────────

    def _on_status(self, status: str) -> None:
        _EMOJI = {
            "LISTENING": "👂",
            "WAKE_WORD_TRIGGERED": "⚡",
            "TRANSCRIBING": "📝",
        }
        tag = _EMOJI.get(status, "❓")
        logger.info("[voice] %s %s", tag, status)

    # ── internal: intent signal ───────────────────────────────

    def _on_intent(self, intent: dict) -> None:
        intent_type = intent.get("type")
        logger.info("[voice] 🎯 intent: %s", intent_type)
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
        worker.done.connect(self._on_chat_done)
        worker.error.connect(self._on_chat_error)
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
            pixmap = getattr(self.window, "current_pixmap", None)
            if pixmap is not None:
                cat_x = (self.window.width() - pixmap.width()) // 2
                cat_y = (self.window.height() - pixmap.height()) // 2
                self._bubble.show_bubble(
                    text, cat_x, cat_y, pixmap.width(), pixmap.height(),
                )
                logger.info("[voice] 💬 bubble-popup show: %r", text[:40])
        if self._anim:
            self._anim.set_overlay("react", 0.5)
        self.window.update()

    def _on_chat_error(self, err: str) -> None:
        if self._anim:
            self._anim.clear_overlay()
        logger.info("[voice] ❌ chat error: %s", err[:60])
        self.window.update()
        logger.warning("[voice-chat] Ollama error: %s", err)
