"""Voice speech bubble — branch-owned asset (myCat Voice Assistant fork).

``SpeechBubble`` is a lightweight ``QPainter``-only overlay painted directly in
the cat's ``paintEvent``, designed for the voice→Ollama→bubble pipeline.
No separate window.  No timer thread issues.

Provenance: written for this branch (TASK-1b ``ce975b6``, extended in TASK-1d
``5207e47``), originally embedded in the upstream file ``speech_bubble.py``.
Moved here verbatim by TASK-3a to restore upstream ownership of that file —
upstream files are read-only for this branch; branch features live in their
own namespace.
"""

from __future__ import annotations

import logging
import time

from PySide6 import QtCore, QtGui

logger = logging.getLogger(__name__)


class SpeechBubble:
    """Manages speech bubble state and paints it via QPainter.

    Designed for the voice→Ollama→bubble pipeline: no separate window, no timers.
    Call :meth:`show` to display text, then paint inside the cat's ``paintEvent``
    via :meth:`paint`.  The bubble auto-hides after *duration* seconds.
    """

    _PADDING_H = 12
    _PADDING_V = 8
    _MAX_WIDTH = 200
    _TAIL_SIZE = 8
    _BORDER_R = 8

    def __init__(self) -> None:
        self._text = ""
        self._visible = False
        self._show_time = 0.0
        self._duration = 0.0
        self._font = QtGui.QFont("sans-serif", 11)
        self._fm = QtGui.QFontMetrics(self._font)

    def show(self, text: str, duration: float = 8.0) -> None:
        self._text = text
        self._visible = True
        self._show_time = time.monotonic()
        self._duration = duration
        logger.info("[bubble] show: %r (%.0fs)", text[:40], duration)

    def bubble_size(self, text: str) -> tuple[int, int]:
        """Return (width, height) the bubble would be for given text."""
        lines = self._wrap_text(text, self._MAX_WIDTH - self._PADDING_H * 2)
        line_h = self._fm.height()
        text_w = max(self._fm.horizontalAdvance(ln) for ln in lines) if lines else 60
        text_h = line_h * len(lines)
        bw = min(text_w + self._PADDING_H * 2, self._MAX_WIDTH)
        bh = text_h + self._PADDING_V * 2
        return bw, bh

    def clear(self) -> None:
        self._visible = False
        self._text = ""

    @property
    def is_active(self) -> bool:
        if not self._visible:
            return False
        if time.monotonic() - self._show_time > self._duration:
            self._visible = False
            return False
        return True

    def paint(self, painter: QtGui.QPainter, cat_x: int, cat_y: int,
              cat_w: int, cat_h: int, *,
              pos: tuple[int, int] | None = None) -> None:
        """Draw the speech bubble.

        When *pos* is ``None`` the bubble is placed above-right of the cat
        sprite.  When *pos* is ``(bx, by)`` it is placed at that window-local
        coordinate (used by the GNOME in-window path).
        """
        if not self.is_active:
            return

        # Word-wrap text
        max_text_w = self._MAX_WIDTH - self._PADDING_H * 2
        lines = self._wrap_text(self._text, max_text_w)
        line_h = self._fm.height()
        text_w = max(self._fm.horizontalAdvance(ln) for ln in lines) if lines else 60
        text_h = line_h * len(lines)

        bw = text_w + self._PADDING_H * 2
        bh = text_h + self._PADDING_V * 2
        bw = min(bw, self._MAX_WIDTH)

        if pos is not None:
            bx, by = pos
        else:
            bx = cat_x + cat_w - bw
            by = cat_y - bh - self._TAIL_SIZE - 6

        painter.save()
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        r = self._BORDER_R
        body = QtCore.QRectF(bx, by, bw, bh)
        path = QtGui.QPainterPath()
        path.addRoundedRect(body, r, r)

        tail_x = bx + 20
        tail = QtGui.QPolygonF([
            QtCore.QPointF(tail_x, by + bh),
            QtCore.QPointF(tail_x + self._TAIL_SIZE, by + bh),
            QtCore.QPointF(tail_x + 4, by + bh + self._TAIL_SIZE),
        ])
        path.addPolygon(tail)

        painter.setPen(QtGui.QPen(QtGui.QColor(180, 180, 180), 1.2))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 220)))
        painter.drawPath(path)

        painter.setPen(QtGui.QColor(40, 40, 40))
        painter.setFont(self._font)
        tx = bx + self._PADDING_H
        ty = by + self._PADDING_V + self._fm.ascent()
        for ln in lines:
            painter.drawText(QtCore.QPointF(tx, ty), ln)
            ty += line_h

        painter.restore()

    def _wrap_text(self, text: str, max_px: int) -> list[str]:
        """Simple word-wrap that fits within max_px pixels."""
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
