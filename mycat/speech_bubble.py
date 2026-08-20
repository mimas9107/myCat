"""Speech bubble overlays for the cat.

Two complementary implementations:

* **BubbleWindow** — a full ``QWidget`` frameless window with typing animation,
  used by the announcement system (reminders, GitHub, calendar, etc.) when the
  *Speak messages in a bubble* setting is on.  Setting: ``[settings] speech_bubble``.

* **SpeechBubble** — a lightweight ``QPainter``-only overlay painted directly in
  the cat's ``paintEvent``, designed for the voice→Ollama→bubble pipeline.
  No separate window.  No timer thread issues.
"""

from __future__ import annotations

import logging
import math
import time

from PySide6 import QtCore, QtGui, QtWidgets

from . import config_store, paths

logger = logging.getLogger(__name__)

SETTINGS_SECTION = "settings"
CONFIG_KEY = "speech_bubble"

# -- BubbleWindow constants ---------------------------------------------------

TYPE_INTERVAL_MS = 35    # per revealed character
HOLD_SECONDS = 10.0      # how long the finished bubble lingers
MAX_TEXT_WIDTH = 480     # wrap long messages to this width
MIN_WIDTH = 120          # the bubble body is never narrower than this
PAD_X, PAD_Y = 10, 4     # side padding >=10px; tight <=5px above/below the glyphs
TAIL_ANGLE_DEG = 25      # apex angle of the pointer aimed at the cat
TAIL_H = 14              # tail length; its width follows from the 15 deg apex
TAIL_W = 2 * TAIL_H * math.tan(math.radians(TAIL_ANGLE_DEG / 2))
TAIL_TIP_MARGIN = 2      # the drawn apex sits this far inside the window's bottom
CORNER = 16              # bubble corner radius
HEAD_GAP = 8             # the drawn tail tip stops 8px above the cat's ears


def bubble_mode_enabled(cfg_file=None) -> bool:
    """Whether the cat speaks messages in a bubble (Settings). Default off = flyby."""
    config = config_store.read_config(cfg_file or paths.config_file())
    if config is not None and config.has_option(SETTINGS_SECTION, CONFIG_KEY):
        try:
            return config.getboolean(SETTINGS_SECTION, CONFIG_KEY)
        except ValueError:
            return False
    return False


def set_bubble_mode(enabled: bool, cfg_file=None) -> None:
    """Persist the Settings 'speak in a bubble' choice."""
    config_store.write_section(
        SETTINGS_SECTION, {CONFIG_KEY: config_store.bool_str(bool(enabled))}, cfg_file or paths.config_file()
    )


# =============================================================================
# BubbleWindow — full QWidget frameless bubble (announcements)
# =============================================================================


class BubbleWindow(QtWidgets.QWidget):
    """A frameless bubble that types ``text`` above ``cat_window`` then vanishes.

    Duck-types :class:`reminder_ui.FlybyWindow` for the announcer: it exposes
    ``start()`` and, via ``WA_DeleteOnClose``, emits ``destroyed`` when it goes —
    so the announcer's pacing (one message at a time) keeps working.
    """

    def __init__(self, cat_window, text, url="", parent=None) -> None:
        flags = QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.Tool
        app = QtWidgets.QApplication.instance()
        platform_name = (app.platformName() or "").lower() if app is not None else ""
        if platform_name != "offscreen":
            flags |= QtCore.Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent, flags)

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        self.cat_window = cat_window
        self.full_text = (str(text) or "").strip()
        self.link_url = str(url or "")
        self.shown_chars = 0
        self.body_w = 40
        self.body_h = 30
        self.tail_x = self.body_w / 2.0
        self.cat_top_cache = None
        self.cat_x_bounds_cache = None

        self.bubble_font = QtGui.QFont()
        self.bubble_font.setPointSize(11)

        self.type_timer = QtCore.QTimer(self)
        self.type_timer.setInterval(TYPE_INTERVAL_MS)
        self.type_timer.timeout.connect(self.on_type)

        self.hold_timer = QtCore.QTimer(self)
        self.hold_timer.setSingleShot(True)
        self.hold_timer.timeout.connect(self.close)

        self.follow_timer = QtCore.QTimer(self)
        self.follow_timer.setInterval(80)
        self.follow_timer.timeout.connect(self.reposition)

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        if not self.full_text:
            QtCore.QTimer.singleShot(0, self.close)
            return
        self.relayout()
        self.show()
        self.raise_()
        self.type_timer.start()
        self.follow_timer.start()

    def on_type(self) -> None:
        self.shown_chars += 1
        self.relayout()
        if self.shown_chars >= len(self.full_text):
            self.type_timer.stop()
            self.hold_timer.start(int(HOLD_SECONDS * 1000))

    # -- geometry -----------------------------------------------------------

    def revealed_text(self) -> str:
        return self.full_text[: self.shown_chars]

    def measured_text_rect(self, text: str) -> QtCore.QRect:
        metrics = QtGui.QFontMetrics(self.bubble_font)
        flags = int(QtCore.Qt.TextFlag.TextWordWrap) | int(QtCore.Qt.AlignmentFlag.AlignLeft)
        return metrics.boundingRect(QtCore.QRect(0, 0, MAX_TEXT_WIDTH, 10000), flags, text or " ")

    def relayout(self) -> None:
        rect = self.measured_text_rect(self.revealed_text() or " ")
        self.body_w = max(rect.width() + 2 * PAD_X, MIN_WIDTH)
        self.body_h = max(rect.height(), 20) + 2 * PAD_Y
        self.resize(self.body_w, self.body_h + TAIL_H)
        self.reposition()
        self.update()

    def cat_ink_top(self) -> int:
        if self.cat_top_cache is not None:
            return self.cat_top_cache
        cat = self.cat_window
        offset = 0
        pixmap = getattr(cat, "current_pixmap", None) or getattr(cat, "first_frame_pixmap", None)
        if pixmap is not None and not pixmap.isNull():
            image = pixmap.toImage()
            pix_top = max(0, (cat.height() - image.height()) // 2)
            center = image.width() // 2
            cols = range(max(0, center - 4), min(image.width(), center + 5))
            for row in range(image.height()):
                if any(QtGui.qAlpha(image.pixel(col, row)) > 12 for col in cols):
                    offset = pix_top + row
                    break
        self.cat_top_cache = offset
        return offset

    def cat_ink_x_bounds(self) -> tuple[int, int]:
        if self.cat_x_bounds_cache is not None:
            return self.cat_x_bounds_cache
        cat = self.cat_window
        left, right = 0, cat.width()
        pixmap = getattr(cat, "current_pixmap", None) or getattr(cat, "first_frame_pixmap", None)
        if pixmap is not None and not pixmap.isNull():
            image = pixmap.toImage()
            pix_left = max(0, (cat.width() - image.width()) // 2)
            rows = range(0, image.height(), 3)
            for col in range(image.width()):
                if any(QtGui.qAlpha(image.pixel(col, row)) > 12 for row in rows):
                    left = pix_left + col
                    break
            for col in range(image.width() - 1, -1, -1):
                if any(QtGui.qAlpha(image.pixel(col, row)) > 12 for row in rows):
                    right = pix_left + col
                    break
        self.cat_x_bounds_cache = (left, right)
        return self.cat_x_bounds_cache

    def reposition(self) -> None:
        cat = self.cat_window
        if cat is None:
            return
        head = cat.mapToGlobal(QtCore.QPoint(cat.width() // 2, self.cat_ink_top()))
        head_x, head_y = head.x(), head.y()
        ink_left, ink_right = self.cat_ink_x_bounds()
        cat_left = cat.mapToGlobal(QtCore.QPoint(ink_left, 0)).x()
        cat_right = cat.mapToGlobal(QtCore.QPoint(ink_right, 0)).x()
        screen = cat.screen() or QtWidgets.QApplication.primaryScreen()
        usable = screen.availableGeometry() if screen is not None else None

        if usable is not None and usable.width() > 0:
            rel = head_x - usable.left()
            third = usable.width() / 3.0
            if rel < third:
                x = cat_left
            elif rel > 2 * third:
                x = cat_right - self.body_w
            else:
                x = head_x - self.body_w / 2.0
        else:
            x = head_x - self.body_w / 2.0

        inset = min(CORNER + TAIL_W, self.body_w / 2.0)
        x = round(x)
        x = min(x, round(head_x - inset))
        x = max(x, round(head_x - (self.body_w - inset)))

        tail_tip = self.body_h + TAIL_H - TAIL_TIP_MARGIN
        y = round(head_y - HEAD_GAP - tail_tip)
        if usable is not None:
            x = max(usable.left(), min(x, usable.right() - self.width()))
            y = max(usable.top(), min(y, usable.bottom() - self.height()))
        self.tail_x = max(inset, min(head_x - x, self.body_w - inset))
        self.move(x, y)

    def bubble_path(self) -> QtGui.QPainterPath:
        body = QtGui.QPainterPath()
        body.addRoundedRect(QtCore.QRectF(1, 1, self.body_w - 2, self.body_h - 2), CORNER, CORNER)
        tip_x = max(TAIL_W, min(self.tail_x, self.body_w - TAIL_W))
        tail = QtGui.QPainterPath()
        tail.moveTo(tip_x - TAIL_W / 2, self.body_h - 2)
        tail.lineTo(tip_x, self.body_h + TAIL_H - TAIL_TIP_MARGIN)
        tail.lineTo(tip_x + TAIL_W / 2, self.body_h - 2)
        tail.closeSubpath()
        return body.united(tail)

    # -- paint --------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        path = self.bubble_path()
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 40, 40), 2))
        painter.setBrush(QtGui.QColor(255, 255, 255, 242))
        painter.drawPath(path)

        painter.setPen(QtGui.QColor(28, 28, 28))
        painter.setFont(self.bubble_font)
        text_area = QtCore.QRect(PAD_X, PAD_Y, self.body_w - 2 * PAD_X, self.body_h - 2 * PAD_Y)
        painter.drawText(
            text_area,
            int(QtCore.Qt.TextFlag.TextWordWrap)
            | int(QtCore.Qt.AlignmentFlag.AlignHCenter)
            | int(QtCore.Qt.AlignmentFlag.AlignVCenter),
            self.revealed_text(),
        )
        painter.end()

        self.setMask(QtGui.QRegion(path.toFillPolygon().toPolygon()))


# =============================================================================
# SpeechBubble — lightweight QPainter overlay (voice pipeline)
# =============================================================================


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
