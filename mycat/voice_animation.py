"""Voice-driven procedural animation overlay for the cat window.

Listens to VoiceWorker signals and applies short-lived QPainter transforms
(scale / translate / dim) on top of whatever frame the CharPack state machine
produces.  No new art assets needed — every reaction is a code-driven
squash/stretch/tint of the existing sprite.

Usage (from PixelCatWindow.__init__):
    from mycat.voice_animation import VoiceAnimationController
    self.voice_anim = VoiceAnimationController(self, self.voice_worker)

Then in paintEvent, after drawPixmap:
    if hasattr(self, "voice_anim"):
        self.voice_anim.apply_overlay(painter, x, y)
"""

import math
import logging

from PySide6 import QtCore, QtGui

logger = logging.getLogger(__name__)

# overlay type constants
_OVERLAY_WAKE = "wake"
_OVERLAY_THINK = "think"
_OVERLAY_REACT = "react"
_CLEAR_TYPES = (None, "clear")


class VoiceAnimationController(QtCore.QObject):
    """Connects to VoiceWorker signals and drives procedural overlay transforms."""

    def __init__(self, window, voice_worker, parent=None):
        super().__init__(parent)
        self.window = window
        self._overlay_type = None
        self._overlay_start = 0.0
        self._overlay_duration = 0.0

        voice_worker.status_changed_signal.connect(self._on_status)
        voice_worker.intent_detected_signal.connect(self._on_intent)
        logger.info("VoiceAnimationController connected")

    # ── slots ────────────────────────────────────────────────

    def _on_status(self, status: str) -> None:
        if status == "WAKE_WORD_TRIGGERED":
            self._trigger(_OVERLAY_WAKE, 0.8)
        elif status == "TRANSCRIBING":
            self._trigger(_OVERLAY_THINK, 1.5)
        elif status == "LISTENING":
            self._clear()
        else:
            logger.debug("[voice-anim] unknown status: %s", status)

    def _on_intent(self, intent: dict) -> None:
        intent_type = intent.get("type", "")
        if intent_type in ("CHAT", "SET_REMINDER"):
            self._trigger(_OVERLAY_REACT, 0.5)
        elif intent_type == "SLEEP":
            # SLEEP handled by main.py (_on_voice_intent_detected); no overlay.
            pass
        else:
            logger.debug("[voice-anim] unhandled intent: %s", intent_type)

    # ── overlay control ──────────────────────────────────────

    def set_overlay(self, overlay_type: str, duration: float) -> None:
        """Public API to manually trigger an overlay (e.g. from voice_chat)."""
        self._trigger(overlay_type, duration)

    def clear_overlay(self) -> None:
        """Public API to manually clear the overlay."""
        self._clear()

    def _trigger(self, overlay_type: str, duration: float) -> None:
        now = self.window._pack_now()
        self._overlay_type = overlay_type
        self._overlay_start = now
        self._overlay_duration = duration
        logger.info("[voice-anim] trigger: %s (%.1fs)", overlay_type, duration)

    def _clear(self) -> None:
        if self._overlay_type is not None:
            logger.info("[voice-anim] overlay cleared")
        self._overlay_type = None

    @property
    def has_active_overlay(self) -> bool:
        if self._overlay_type is None:
            return False
        now = self.window._pack_now()
        return (now - self._overlay_start) < self._overlay_duration

    # ── overlay params (per-type procedural transforms) ──────

    def _overlay_params(self):
        """Return (sx, sy, dx, dy, dim) for the current overlay frame."""
        now = self.window._pack_now()
        age = now - self._overlay_start
        t = min(age / self._overlay_duration, 1.0) if self._overlay_duration > 0 else 1.0

        if self._overlay_type == _OVERLAY_WAKE:
            # Bounce: quick expand then ease back
            ease = math.sin(t * math.pi)          # 0→1→0
            return (1.0, 1.0 + 0.15 * ease, 0, -15 * ease, 0)

        if self._overlay_type == _OVERLAY_THINK:
            # Subtle head-tilt: held for duration, ease in/out
            ease = math.sin(t * math.pi)
            return (0.95, 1.0, 5 * ease, 0, 0)

        if self._overlay_type == _OVERLAY_REACT:
            # Small bounce
            ease = math.sin(t * math.pi)
            return (1.0, 1.0 + 0.08 * ease, 0, -10 * ease, 0)

        return (1.0, 1.0, 0, 0, 0)

    # ── paint hook ───────────────────────────────────────────

    def apply_overlay(self, painter: QtGui.QPainter, x: int, y: int) -> None:
        """Called from paintEvent after drawPixmap.  Applies procedural transform."""
        if not self.has_active_overlay:
            return

        sx, sy, dx, dy, dim = self._overlay_params()
        pixmap = self.window.current_pixmap
        w, h = pixmap.width(), pixmap.height()

        # Anchor at bottom-centre so squash grows from the feet
        anchor_x = x + w / 2
        anchor_y = y + h

        painter.save()
        painter.translate(anchor_x, anchor_y)
        painter.scale(sx, sy)
        painter.translate(-anchor_x, -anchor_y)
        painter.drawPixmap(x, y, pixmap)
        painter.restore()

        if dim > 0:
            painter.setCompositionMode(
                QtGui.QPainter.CompositionMode.CompositionMode_SourceAtop
            )
            painter.fillRect(
                self.window.rect(), QtGui.QColor(0, 0, 0, int(dim * 255))
            )
            painter.setCompositionMode(
                QtGui.QPainter.CompositionMode.CompositionMode_SourceOver
            )
