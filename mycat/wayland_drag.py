"""Wayland & Cross-platform Native Window Dragging Plugin for myCat.

Hooks into PixelCatWindow via QObject.installEventFilter without modifying
main.py's mouse event logic. Uses QWindow.startSystemMove() to delegate
window dragging to the Wayland Compositor (Sway, GNOME Mutter, Hyprland, KDE)
or X11 Window Manager.
"""

import logging
from PySide6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)


class WaylandDragHandler(QtCore.QObject):
    """Event filter that enables native Wayland xdg_toplevel.move dragging."""

    def __init__(self, window: QtWidgets.QWidget):
        super().__init__(window)
        self.window = window
        self._dragging = False
        # Attach event filter to the cat window
        self.window.installEventFilter(self)
        logger.info("WaylandDragHandler attached to window (native startSystemMove enabled)")

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched is self.window:
            event_type = event.type()

            if event_type == QtCore.QEvent.Type.MouseButtonPress:
                mouse_event: QtGui.QMouseEvent = event
                if mouse_event.button() == QtCore.Qt.MouseButton.LeftButton:
                    window_handle = self.window.windowHandle()
                    if window_handle and hasattr(window_handle, "startSystemMove"):
                        try:
                            started = window_handle.startSystemMove()
                            logger.debug("startSystemMove initiated: %s", started)
                            if started:
                                self._dragging = True
                        except Exception as exc:
                            logger.warning("startSystemMove failed: %s", exc)

            elif event_type == QtCore.QEvent.Type.MouseButtonRelease:
                mouse_event: QtGui.QMouseEvent = event
                if mouse_event.button() == QtCore.Qt.MouseButton.LeftButton and self._dragging:
                    self._dragging = False
                    # Save position when native drag ends
                    if hasattr(self.window, "_save_position"):
                        try:
                            self.window._save_position()
                        except Exception as exc:
                            logger.warning("Failed to save position after drag: %s", exc)

        # Return False so original mousePressEvent/mouseReleaseEvent in main.py still run
        return False


def attach_wayland_drag_handler(window: QtWidgets.QWidget) -> WaylandDragHandler | None:
    """Convenience function to attach WaylandDragHandler to PixelCatWindow."""
    try:
        return WaylandDragHandler(window)
    except Exception as exc:
        logger.warning("Failed to attach WaylandDragHandler: %s", exc)
        return None
