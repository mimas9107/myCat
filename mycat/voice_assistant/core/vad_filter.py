import math
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


class VoiceVAD:
    """Band-energy adaptive VAD (Layer 1 voice filter, PLAN-3c).

    Frames each chunk (30ms window / 10ms hop, Blackman), measures the
    300-3400Hz in-band RMS via rfft, tracks the noise floor with an EMA that
    only ingests non-speech frames (score < snr_off, never while speaking),
    and gates on SNR with a hysteresis state machine plus minimum-speech
    persistence.  Any steady signal present during the first ``bootstrap_ms``
    is treated as ambient noise so the floor is meaningful immediately after
    construction.

    The plan's ported asset was a Hamming window; Phase 1 corpus testing
    showed its -41dB sidelobes let strong sub-band tones (fan rumble) leak
    into the band at ~1.7x the noise floor — right at snr_on.  Blackman's
    -58dB sidelobes drop that leakage to ~0.07x, so the band filter actually
    rejects what it exists to reject.

    ``snr_on`` defaults to 2.25 — chosen from the ESP32 fixture corpus sweep
    (TASK-3c Phase 1): sustained in-band SNR of real utterances there is
    ~2.3-2.7x, while steady/transient noise stays under ~2x; the plan's
    initial 3.0 missed quiet-speech fixtures and <=2.0 let noise swells cross.
    Frame RMS passes through an EMA smoother (``smooth_alpha``) before scoring,
    which keeps hovering speech scores stable enough to accrue persistence.
    """

    _LEAK_HOPS = 1.0

    def __init__(self, sample_rate=16000, freq_min=300, freq_max=3400,
                 snr_on=2.25, snr_off=1.5, min_speech_ms=200, release_ms=300,
                 floor_alpha=0.01, smooth_alpha=0.3,
                 frame_ms=30, hop_ms=10, bootstrap_ms=300):
        self.sample_rate = sample_rate
        self.freq_min = freq_min
        self.freq_max = freq_max
        self.snr_on = snr_on
        self.snr_off = snr_off
        self.min_speech_ms = min_speech_ms
        self.release_ms = release_ms
        self.floor_alpha = floor_alpha
        self.smooth_alpha = smooth_alpha
        self.frame_size = int(sample_rate * frame_ms / 1000)
        self.hop_size = int(sample_rate * hop_ms / 1000)
        self.window = np.blackman(self.frame_size)
        freqs = np.fft.rfftfreq(self.frame_size, d=1.0 / sample_rate)
        self._band = (freqs >= freq_min) & (freqs <= freq_max)

        self._bootstrap_frames = max(1, int(bootstrap_ms / hop_ms))
        self._bootstrap_alpha = 0.2

        self._floor = None
        self._frames_seen = 0
        self._speech_acc_ms = 0.0
        self._release_acc_ms = 0.0
        self._rms_smooth = None
        self.speaking = False
        self.last_score = 0.0

    @property
    def noise_floor(self) -> float:
        """Current in-band noise floor estimate (for debugging/logging)."""
        return self._floor if self._floor is not None else 0.0

    def reset(self):
        """Clears all adaptive state (floor, counters, hysteresis state)."""
        self._floor = None
        self._frames_seen = 0
        self._speech_acc_ms = 0.0
        self._release_acc_ms = 0.0
        self._rms_smooth = None
        self.speaking = False
        self.last_score = 0.0

    def _band_rms(self, frame: np.ndarray) -> float:
        spectrum = np.fft.rfft(frame * self.window)
        return float(np.sqrt(np.mean(np.abs(spectrum[self._band]) ** 2)))

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Feeds one chunk through framing + scoring + hysteresis state machine.

        Returns True while speech is active. Chunks shorter than one frame
        leave all state untouched and report the current state.
        """
        if audio_chunk is None:
            return self.speaking
        samples = np.asarray(audio_chunk, dtype=np.float64)
        n = len(samples)
        if n < self.frame_size:
            return self.speaking

        hop_ms = 1000.0 * self.hop_size / self.sample_rate
        for start in range(0, n - self.frame_size + 1, self.hop_size):
            rms = self._band_rms(samples[start:start + self.frame_size])
            if self.smooth_alpha > 0.0:
                if self._rms_smooth is None:
                    self._rms_smooth = rms
                else:
                    self._rms_smooth += (1.0 - self.smooth_alpha) * (rms - self._rms_smooth)
                rms = self._rms_smooth
            self._update(rms, hop_ms)
        return self.speaking

    def _update(self, rms: float, hop_ms: float):
        self._frames_seen += 1
        if self._floor is None:
            self._floor = rms
            return

        self.last_score = rms / max(self._floor, 1e-9)

        if self._frames_seen <= self._bootstrap_frames:
            self._floor += self._bootstrap_alpha * (rms - self._floor)
            return

        if not self.speaking:
            if self.last_score >= self.snr_on:
                self._speech_acc_ms += hop_ms
            else:
                # Leaky decay instead of hard reset: scores hovering around
                # snr_on (e.g. quiet speech over a noisy floor) still accrue.
                self._speech_acc_ms = max(0.0, self._speech_acc_ms - self._LEAK_HOPS * hop_ms)
            if self._speech_acc_ms >= self.min_speech_ms:
                self.speaking = True
                self._release_acc_ms = 0.0
            elif self.last_score < self.snr_off:
                self._floor += self.floor_alpha * (rms - self._floor)
        else:
            if self.last_score < self.snr_off:
                self._release_acc_ms += hop_ms
            else:
                self._release_acc_ms = max(0.0, self._release_acc_ms - self._LEAK_HOPS * hop_ms)
            if self._release_acc_ms >= self.release_ms:
                self.speaking = False
                self._speech_acc_ms = 0.0
