import numpy as np


class EnergyVAD:
    """Lightweight Energy-based Voice Activity Detection (VAD)."""

    def __init__(self, threshold=50000.0):
        self.threshold = threshold

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Determines if the given audio chunk contains speech based on RMS."""
        if audio_chunk is None or len(audio_chunk) == 0:
            return False

        rms = math.sqrt(np.sum(audio_chunk.astype(np.float64) ** 2) / len(audio_chunk))
        return float(rms) > float(self.threshold)

    def get_energy(self, audio_chunk: np.ndarray) -> float:
        """Returns the RMS of the chunk for debugging."""
        if audio_chunk is None or len(audio_chunk) == 0:
            return 0.0
        return float(math.sqrt(np.sum(audio_chunk.astype(np.float64) ** 2) / len(audio_chunk)))
