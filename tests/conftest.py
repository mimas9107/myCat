"""Shared pytest fixtures. Qt runs headless via the offscreen platform."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Swap the microphone for a WAV fixture: window-spawning tests trigger the ASR
# warm-start, which would otherwise open PyAudio and abort on mic-less machines.
os.environ.setdefault(
    "MYCAT_AUDIO_WAV",
    os.path.join(os.path.dirname(__file__), "fixtures", "audio", "pos_heymiaomiao.wav"),
)

import pytest
from PySide6 import QtWidgets


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app
