"""Voice-specific char assets (think.png, listen.png).

Extends the char pack with voice-reaction images without modifying the
upstream ``CharPack`` class.  Falls back gracefully when assets are absent.
"""

from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui

from .char_pack import CharSource, pixmap_from_bytes

logger = logging.getLogger(__name__)

_VOICE_ASSETS = ("think.png", "listen.png", "yawn.png")


class VoiceCharPack:
    """Loads optional voice-specific static images from a char archive.

    Automatically matches the char's native render scale by reading
    ``static.png`` dimensions and comparing to the target render size.
    Each asset is ``None`` when absent from the ZIP/folder.
    """

    def __init__(self, char_path, target_width: int, target_height: int):
        self.think: QtGui.QPixmap | None = None
        self.listen: QtGui.QPixmap | None = None
        self._load(char_path, target_width, target_height)

    def _load(self, char_path, target_width: int, target_height: int) -> None:
        try:
            with CharSource(char_path) as archive:
                names = archive.names()
                # Compute scale from static.png native size vs target render size
                static_raw = pixmap_from_bytes(archive.read("static.png"))
                native_w = static_raw.width() or target_width
                native_h = static_raw.height() or target_height
                scale = min(target_width / native_w, target_height / native_h, 1.0)

                for asset in _VOICE_ASSETS:
                    if asset not in names:
                        continue
                    raw = pixmap_from_bytes(archive.read(asset))
                    if scale != 1.0:
                        raw = raw.scaled(
                            max(1, round(raw.width() * scale)),
                            max(1, round(raw.height() * scale)),
                            QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                            QtCore.Qt.TransformationMode.SmoothTransformation,
                        )
                    setattr(self, asset.replace(".png", ""), raw)
                    logger.info("[voice-char] loaded %s (%dx%d)",
                                asset, raw.width(), raw.height())
        except Exception as exc:
            logger.debug("[voice-char] load failed: %s", exc)

    def get(self, overlay_type: str) -> QtGui.QPixmap | None:
        """Return the pixmap for an overlay type, or None."""
        return getattr(self, overlay_type, None)
