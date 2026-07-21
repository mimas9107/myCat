import collections
import numpy as np
import pyaudio


class AudioStreamManager:
    """Manages PyAudio input stream and maintains a ring buffer for historical audio."""

    def __init__(self, sample_rate=16000, chunk_duration_ms=100, buffer_seconds=3):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * (chunk_duration_ms / 1000.0))
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
