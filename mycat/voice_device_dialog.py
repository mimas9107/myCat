import logging

from PySide6 import QtWidgets

logger = logging.getLogger(__name__)


class VoiceDeviceDialog(QtWidgets.QDialog):
    """Dialog for selecting audio input device."""

    def __init__(self, parent=None, current_device_index=None):
        super().__init__(parent)
        self.setWindowTitle("Voice Input Device")
        self.setMinimumWidth(400)
        self._current_index = current_device_index
        self._selected_index = current_device_index
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        label = QtWidgets.QLabel("Select audio input device:")
        layout.addWidget(label)

        self._combo = QtWidgets.QComboBox()
        layout.addWidget(self._combo)

        self._populate_devices()

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_devices(self):
        try:
            from mycat.voice_assistant.core.audio_stream import AudioStreamManager
            devices = AudioStreamManager.list_devices()
        except Exception as e:
            logger.error("Failed to list audio devices: %s", e)
            self._combo.addItem("No devices available", userData=None)
            return

        if not devices:
            self._combo.addItem("No input devices found", userData=None)
            return

        for dev in devices:
            text = f"{dev['index']}: {dev['name']}"
            self._combo.addItem(text, userData=dev["index"])

        if self._current_index is not None:
            idx = self._combo.findData(self._current_index)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

    def selected_device_index(self) -> int | None:
        return self._combo.currentData()

    @staticmethod
    def get_device(parent=None, current_device_index=None) -> int | None:
        """Show dialog and return selected device index, or None if cancelled."""
        dialog = VoiceDeviceDialog(parent, current_device_index)
        if dialog.exec() == dialog.Accepted:
            return dialog.selected_device_index()
        return None
