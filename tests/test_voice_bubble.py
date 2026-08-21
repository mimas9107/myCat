"""Voice branch's own SpeechBubble (mycat/voice_bubble.py).

Branch-owned asset moved out of the upstream ``speech_bubble.py`` by TASK-3a.
Unlike the upstream ``BubbleWindow`` (a real top-level widget), ``SpeechBubble``
is a QPainter-only overlay painted inside the cat's ``paintEvent`` — these
tests exercise sizing, the show/clear/expiry lifecycle and painting smoke.
"""

from PySide6 import QtGui, QtWidgets

from mycat.voice_bubble import SpeechBubble


def test_bubble_size_wraps_and_caps(qapp):
    bubble = SpeechBubble()
    short_w, short_h = bubble.bubble_size("hi")
    long_w, long_h = bubble.bubble_size(
        "a very long sentence that certainly cannot fit on a single line "
        "because it keeps going and going well past two hundred pixels"
    )
    assert long_h > short_h  # wrapped onto more lines
    assert long_w <= SpeechBubble._MAX_WIDTH  # width capped
    assert short_w > SpeechBubble._PADDING_H * 2


def test_show_clear_lifecycle(qapp):
    bubble = SpeechBubble()
    assert bubble.is_active is False
    bubble.show("meow")
    assert bubble.is_active is True
    bubble.clear()
    assert bubble.is_active is False
    assert bubble._text == ""


def test_auto_expiry_after_duration(qapp):
    import time

    bubble = SpeechBubble()
    bubble.show("fleeting", duration=0.0)
    time.sleep(0.01)  # let monotonic clock pass the zero duration
    assert bubble.is_active is False


def test_paint_smoke_both_modes(qapp):
    bubble = SpeechBubble()
    image = QtGui.QImage(300, 300, QtGui.QImage.Format.Format_ARGB32)
    painter = QtGui.QPainter(image)

    bubble.show("paint me above the cat")
    bubble.paint(painter, 100, 200, 64, 64)  # default above-right placement
    bubble.paint(painter, 0, 0, 64, 64, pos=(10, 10))  # explicit window-local
    painter.end()

    bubble.clear()
    painter2 = QtGui.QPainter(image)
    bubble.paint(painter2, 0, 0, 64, 64)  # inactive → silent no-op
    painter2.end()


def test_wrap_text_respects_max_px(qapp):
    bubble = SpeechBubble()
    text = "word " * 40
    for line in bubble._wrap_text(text, 150):
        assert bubble._fm.horizontalAdvance(line) <= 150 or " " not in line
