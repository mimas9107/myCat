import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_FILENAME = "voice_device.json"


def _get_device_config_path() -> Path:
    config_dir = Path.home() / ".config" / "mycat"
    return config_dir / _CONFIG_FILENAME


def load_saved_device_index() -> int | None:
    """Load saved device index from config, or None if not set."""
    config_path = _get_device_config_path()
    if not config_path.exists():
        return None
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("device_index")
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load voice device config: %s", e)
        return None


def save_device_index(device_index: int | None) -> bool:
    """Save device index to config. Returns True on success."""
    config_path = _get_device_config_path()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"device_index": device_index}
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("Saved voice device_index=%s", device_index)
        return True
    except OSError as e:
        logger.error("Failed to save voice device config: %s", e)
        return False
