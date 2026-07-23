"""Floating speech-bubble popup (Qt.ToolTip window).

On Wayland this maps to xdg_popup — a transient window that floats over the
parent without being managed as a tile by the compositor.
"""

from __future__ import annotations

import logging
import time

from PySide6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)

_PADDING_H = 12
_PADDING_V = 8
_MAX_WIDTH = 200
_TAIL_SIZE = 8
_BORDER_R = 8


class BubblePopup(QtWidgets.QWidget):
    """Frameless tooltip window that displays a speech bubble near the cat."""

    def __init__(self, parent_window):
        win_flags = (
            QtCore.Qt.WindowType.ToolTip
            | QtCore.Qt.WindowType.FramelessWindowHint
        )
        super().__init__(parent_window, win_flags)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._text = ""
        self._show_time = 0.0
        self._duration = 0.0
        self._below = False
        self._font = QtGui.QFont("sans-serif", 11)
        self._fm = QtGui.QFontMetrics(self._font)

        self._hide_timer = QtCore.QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._on_timeout)

    # ── public API ───────────────────────────────────────────

    def show_bubble(self, text: str, cat_x: int, cat_y: int,
                    cat_w: int, cat_h: int, duration: float = 8.0) -> None:
        """Calculate layout, position the popup near the cat, and show it."""
        self._text = text
        self._show_time = time.monotonic()
        self._duration = duration

        bw, bh, bx, by, self._below = self._calc_layout(cat_x, cat_y, cat_w, cat_h)
        self._position_near_cat(bx, by, bw, bh)

        popup_h = bh + _TAIL_SIZE if self._below else bh + _TAIL_SIZE
        self.resize(bw, popup_h)
        self.show()
        self._hide_timer.start(int(duration * 1000))
        logger.info("[bubble-popup] shown %r (%.0fs, above=%s)",
                    text[:40], duration, not self._below)

    def hide_bubble(self) -> None:
        self._hide_timer.stop()
        self.hide()

    @property
    def is_active(self) -> bool:
        if not self.isVisible():
            return False
        return time.monotonic() - self._show_time < self._duration

    # ── layout ───────────────────────────────────────────────

    def _calc_layout(self, cat_x, cat_y, cat_w, cat_h):
        """Return (bw, bh, bx, by, below) in cat-window coordinates."""
        lines = self._wrap_text(self._text)
        line_h = self._fm.height()
        text_w = max(self._fm.horizontalAdvance(ln) for ln in lines) if lines else 60
        text_h = line_h * len(lines)

        bw = min(text_w + _PADDING_H * 2, _MAX_WIDTH)
        bh = text_h + _PADDING_V * 2
        bx = cat_x + cat_w - bw

        above_by = cat_y - bh - _TAIL_SIZE - 6
        below = above_by < 4
        if below:
            by = cat_y + cat_h + _TAIL_SIZE + 6
        else:
            by = above_by
        return bw, bh, bx, by, below

    def _position_near_cat(self, bx, by, bw, bh):
        """Move this popup to screen coordinates near the cat."""
        parent_pos = self.parent().mapToGlobal(QtCore.QPoint(0, 0))
        sx = parent_pos.x() + bx
        sy = parent_pos.y() + by
        self.move(sx, sy)

    # ── paint ────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        if self._below:
            body_rect = QtCore.QRectF(0, _TAIL_SIZE, w, h - _TAIL_SIZE)
            tail = QtGui.QPolygonF([
                QtCore.QPointF(20, _TAIL_SIZE),
                QtCore.QPointF(20 + _TAIL_SIZE, _TAIL_SIZE),
                QtCore.QPointF(24, 0),
            ])
        else:
            body_rect = QtCore.QRectF(0, 0, w, h - _TAIL_SIZE)
            tail = QtGui.QPolygonF([
                QtCore.QPointF(20, h - _TAIL_SIZE),
                QtCore.QPointF(20 + _TAIL_SIZE, h - _TAIL_SIZE),
                QtCore.QPointF(24, h),
            ])

        r = _BORDER_R
        path = QtGui.QPainterPath()
        path.addRoundedRect(body_rect, r, r)
        path.addPolygon(tail)

        painter.setPen(QtGui.QPen(QtGui.QColor(180, 180, 180), 1.2))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 220)))
        painter.drawPath(path)

        painter.setPen(QtGui.QColor(40, 40, 40))
        painter.setFont(self._font)
        tx = _PADDING_H
        ty = _PADDING_V + self._fm.ascent()
        for ln in self._wrap_text(self._text):
            painter.drawText(QtCore.QPointF(tx, ty), ln)
            ty += self._fm.height()

    # ── helpers ──────────────────────────────────────────────

    def _wrap_text(self, text: str) -> list[str]:
        max_px = _MAX_WIDTH - _PADDING_H * 2
        words = text.split()
        lines: list[str] = []
        current = ""
        for w in words:
            test = f"{current} {w}".strip()
            if self._fm.horizontalAdvance(test) > max_px and current:
                lines.append(current)
                current = w
            else:
                current = test
        if current:
            lines.append(current)
        return lines or [""]

    def _on_timeout(self) -> None:
        self.hide()
