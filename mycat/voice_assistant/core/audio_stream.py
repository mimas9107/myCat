import collections
import logging
import platform

import numpy as np
import pyaudio

logger = logging.getLogger(__name__)


class AudioStreamManager:
    """Manages PyAudio input stream and maintains a ring buffer for historical audio."""

    def __init__(self, sample_rate=16000, chunk_duration_ms=100, buffer_seconds=3, device_index=None):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * (chunk_duration_ms / 1000.0))
        if device_index is None:
            device_index = AudioStreamManager.prefer_suitable_device()
        self.device_index = device_index
        max_chunks = int((buffer_seconds * 1000) / chunk_duration_ms)

        self.ring_buffer = collections.deque(maxlen=max_chunks)
        self.p = None
        self.stream = None
        self._is_running = False

    def _audio_callback(self, in_data, frame_count, time_info, status):
        audio_chunk = np.frombuffer(in_data, dtype=np.int16)
        self.ring_buffer.append(audio_chunk)
        return (None, pyaudio.paContinue)

    def start(self):
        """Starts PyAudio background audio capture."""
        if self._is_running:
            return
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback,
        )
        self._is_running = True
        self.stream.start_stream()

    def stop(self):
        """Stops PyAudio stream cleanly."""
        if not self._is_running:
            return
        self._is_running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        if self.p:
            self.p.terminate()
            self.p = None

    def get_buffered_audio(self) -> np.ndarray:
        """Concatenates all audio chunks in the ring buffer into a 1D NumPy array."""
        if len(self.ring_buffer) == 0:
            return np.array([], dtype=np.int16)
        return np.concatenate(list(self.ring_buffer))

    def get_recent_chunk(self, duration_sec: float = 0.1) -> np.ndarray:
        """Returns the most recent chunk of audio (default 0.1 seconds)."""
        num_samples = int(self.sample_rate * duration_sec)
        if len(self.ring_buffer) == 0:
            return np.array([], dtype=np.int16)
        recent_chunks = list(self.ring_buffer)[-num_samples:]
        if not recent_chunks:
            return np.array([], dtype=np.int16)
        return np.concatenate(recent_chunks)

    @staticmethod
    def list_devices() -> list[dict]:
        """Lists all available audio input devices."""
        p = None
        try:
            p = pyaudio.PyAudio()
            devices = []
            for i in range(p.get_device_count()):
                dev_info = p.get_device_info_by_index(i)
                if dev_info["maxInputChannels"] > 0:
                    devices.append({
                        "index": i,
                        "name": dev_info["name"],
                        "channels": dev_info["maxInputChannels"],
                        "sample_rate": int(dev_info["defaultSampleRate"]),
                    })
            return devices
        except Exception as e:
            logger.error("Failed to list audio devices: %s", e)
            return []
        finally:
            if p:
                p.terminate()

    @staticmethod
    def prefer_suitable_device() -> int | None:
        """Auto-detects and returns the best input device index, or None if none found."""
        devices = AudioStreamManager.list_devices()
        if not devices:
            logger.warning("No audio input devices found")
            return None

        system = platform.system()

        if system == "Linux":
            for dev in devices:
                name = dev["name"].lower()
                if "pulse" in name or "pipewire" in name or "default" in name:
                    logger.info("Selected PulseAudio/PipeWire device: %s (index=%d)", dev["name"], dev["index"])
                    return dev["index"]
            for dev in devices:
                name = dev["name"].lower()
                if "hw:" in name or "plughw" in name:
                    logger.warning("Skipping raw ALSA device: %s", dev["name"])
                    continue
                logger.info("Selected fallback device: %s (index=%d)", dev["name"], dev["index"])
                return dev["index"]

        if devices:
            logger.info("Selected default device: %s (index=%d)", devices[0]["name"], devices[0]["index"])
            return devices[0]["index"]

        return None
