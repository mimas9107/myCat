"""Voice-driven procedural animation overlay for the cat window.

Listens to VoiceWorker signals and applies short-lived QPainter transforms
(scale / translate / dim) on top of whatever frame the CharPack state machine
produces.  No new art assets needed — every reaction is a code-driven
squash/stretch/tint of the existing sprite.

Usage (from VoiceBridge):
    from mycat.voice_animation import VoiceAnimationController
    self.voice_anim = VoiceAnimationController(
        window=window, voice_worker=worker, time_fn=window.pack_now,
    )

Then in paintEvent, after drawPixmap:
    if hasattr(self, "voice_anim"):
        self.voice_anim.apply_overlay(painter, x, y)

Debug logging
-------------
Set env ``VOICE_BRIDGE_DEBUG=1`` to trace time_fn callback usage.
After 3 consecutive clean commits, flip to 0 (or remove).
"""

import logging
import math
import os

from PySide6 import QtCore, QtGui

logger = logging.getLogger(__name__)

_DEBUG = os.environ.get("VOICE_BRIDGE_DEBUG", "0") == "1"

def _dbg(msg: str, *args) -> None:
    if _DEBUG:
        logger.info("[voice-anim] " + msg, *args)

# overlay type constants
_OVERLAY_WAKE = "wake"
_OVERLAY_THINK = "think"
_OVERLAY_REACT = "react"
_OVERLAY_YAWN = "yawn"
_CLEAR_TYPES = (None, "clear")


class VoiceAnimationController(QtCore.QObject):
    """Connects to VoiceWorker signals and drives procedural overlay transforms."""

    _YAWN_IDLE_DEFAULT = 30.0  # seconds of silence before yawn

    def __init__(self, window, voice_worker, time_fn=None,
                 overlay_enabled: bool = True, idle_yawn_after: float = None,
                 parent=None):
        super().__init__(parent)
        self.window = window
        self._overlay_type = None
        self._overlay_start = 0.0
        self._overlay_duration = 0.0
        self._overlay_enabled = overlay_enabled
        self._voice_pack = None  # VoiceCharPack, set via set_voice_pack()

        # idle yawn timer
        self._idle_yawn_after = idle_yawn_after or self._YAWN_IDLE_DEFAULT
        self._idle_timer = QtCore.QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._on_idle_yawn)

        # time_fn: callable returning current time in seconds.
        # Injected by VoiceBridge to decouple from window._pack_now().
        if time_fn is not None:
            self._time_fn = time_fn
            _dbg("time_fn injected: %s", time_fn)
        else:
            # backward compat fallback — deprecation path
            self._time_fn = window._pack_now
            _dbg("time_fn NOT injected, falling back to window._pack_now()")

        voice_worker.status_changed_signal.connect(self._on_status)
        voice_worker.intent_detected_signal.connect(self._on_intent)
        self._reset_idle_timer()
        logger.info("VoiceAnimationController connected (overlay=%s, idle_yawn=%.0fs)",
                     "ON" if self._overlay_enabled else "OFF",
                     self._idle_yawn_after)

    # ── time source ───────────────────────────────────────────

    def _now(self) -> float:
        return self._time_fn()

    # ── voice char pack ─────────────────────────────────────

    def set_voice_pack(self, voice_pack) -> None:
        """Set VoiceCharPack for static sprite overlays."""
        self._voice_pack = voice_pack

    # ── slots ────────────────────────────────────────────────

    def _reset_idle_timer(self) -> None:
        """Restart the idle yawn countdown.  Called on every voice activity."""
        if self._idle_yawn_after > 0:
            self._idle_timer.start(int(self._idle_yawn_after * 1000))

    def _on_idle_yawn(self) -> None:
        """Fires when no voice activity for _idle_yawn_after seconds."""
        if self._voice_pack is not None and self._voice_pack.get("yawn") is not None:
            self._trigger(_OVERLAY_YAWN, 3.0)
            logger.info("[voice-anim] 😴 idle yawn overlay (3s)")

    def _on_status(self, status: str) -> None:
        self._reset_idle_timer()
        if status == "WAKE_WORD_TRIGGERED":
            self._trigger(_OVERLAY_WAKE, 0.8)
            logger.info("[voice-anim] ⚡ wake overlay (0.8s)")
        elif status == "TRANSCRIBING":
            self._trigger(_OVERLAY_THINK, 1.5)
            logger.info("[voice-anim] 🤔 think overlay (1.5s)")
        elif status == "LISTENING":
            self._clear()
            logger.info("[voice-anim] 👂 back to listening")
        else:
            logger.debug("[voice-anim] unknown status: %s", status)

    def _on_intent(self, intent: dict) -> None:
        self._reset_idle_timer()
        intent_type = intent.get("type", "")
        if intent_type in ("CHAT", "SET_REMINDER"):
            self._trigger(_OVERLAY_REACT, 0.5)
        elif intent_type == "SLEEP":
            # SLEEP handled by VoiceBridge intent dispatch; no overlay.
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
        if not self._overlay_enabled:
            return
        now = self._now()
        self._overlay_type = overlay_type
        self._overlay_start = now
        self._overlay_duration = duration
        _dbg("trigger: %s (%.1fs) via %s", overlay_type, duration, self._time_fn)

    def _clear(self) -> None:
        if self._overlay_type is not None:
            _dbg("overlay cleared")
        self._overlay_type = None

    @property
    def has_active_overlay(self) -> bool:
        if self._overlay_type is None:
            return False
        now = self._now()
        return (now - self._overlay_start) < self._overlay_duration

    @property
    def overlay_replaces_face(self) -> bool:
        """True when active overlay has a VoiceCharPack sprite → replace current pixmap."""
        if not self.has_active_overlay:
            return False
        if self._voice_pack is None:
            return False
        return self._voice_pack.get(self._overlay_type) is not None

    # ── overlay params (per-type procedural transforms) ──────

    def _overlay_params(self):
        """Return (sx, sy, dx, dy, dim) for the current overlay frame."""
        now = self._now()
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

        if self._overlay_type == _OVERLAY_YAWN:
            # Slow squash: mouth-open is wider, ease is half-sine
            ease = math.sin(t * math.pi * 0.5)    # 0→1
            return (1.0 + 0.1 * ease, 1.0 - 0.05 * ease, 0, 0, 0)

        return (1.0, 1.0, 0, 0, 0)

    # ── paint hook ───────────────────────────────────────────

    def apply_overlay(self, painter: QtGui.QPainter, x: int, y: int) -> None:
        """Called from paintEvent after drawPixmap.

        If a VoiceCharPack sprite exists for the current overlay type, draw
        it centred on the cat.  Otherwise fall back to the procedural
        scale/translate transform.
        """
        if not self.has_active_overlay:
            return

        # Prefer voice char sprite when available
        if self._voice_pack is not None:
            sprite = self._voice_pack.get(self._overlay_type)
            if sprite is not None:
                # Centre the sprite on the cat
                sx = x + (self.window.current_pixmap.width() - sprite.width()) // 2
                sy = y + (self.window.current_pixmap.height() - sprite.height()) // 2
                painter.drawPixmap(sx, sy, sprite)
                return

        # Fallback: procedural transform
        sx, sy, dx, dy, dim = self._overlay_params()
        pixmap = self.window.current_pixmap
        w, h = pixmap.width(), pixmap.height()

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
