import numpy as np


class EnergyVAD:
    """Lightweight Energy-based Voice Activity Detection (VAD)."""

    def __init__(self, threshold=50000.0):
        self.threshold = threshold

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Determines if the given audio chunk contains speech based on mean energy."""
        if audio_chunk is None or len(audio_chunk) == 0:
            return False

        # Calculate mean energy (sum of squares converted to float to avoid overflow)
        energy = np.sum(audio_chunk.astype(np.float64) ** 2) / len(audio_chunk)
        return float(energy) > float(self.threshold)

    def get_energy(self, audio_chunk: np.ndarray) -> float:
        """Returns the mean energy of the chunk for debugging."""
        if audio_chunk is None or len(audio_chunk) == 0:
            return 0.0
        return float(np.sum(audio_chunk.astype(np.float64) ** 2) / len(audio_chunk))
