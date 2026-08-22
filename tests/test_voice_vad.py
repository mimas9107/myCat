"""VoiceVAD synthetic-signal unit checks + fixture behavioral verification.

Covers PLAN-3c test-matrix rows 1-5 (deterministic synthetic inputs) plus the
ESP32 fixture corpus check.  Signals are fed as 100ms int16 chunks through the
same is_speech() path the VoiceWorker uses.
"""

import os
import wave

import numpy as np

from mycat.voice_assistant.core.vad_filter import VoiceVAD

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "audio")
SR = 16000
CHUNK = 1600


def _ambient(seconds=0.6, seed=7, level=30):
    rng = np.random.default_rng(seed)
    return rng.normal(0, level, int(SR * seconds)).astype(np.int16)


def _tone(freq, seconds, amp=3000):
    t = np.arange(int(SR * seconds)) / SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def _feed(vad, signal):
    return [vad.is_speech(signal[i:i + CHUNK]) for i in range(0, len(signal) - vad.frame_size, CHUNK)]


# Row 1: 440Hz sine after ambient lead-in must trigger.
def test_sine_triggers():
    vad = VoiceVAD()
    states = _feed(vad, np.concatenate([_ambient(), _tone(440, 1.0)]))
    assert any(states)


# Row 2: continuous white noise must never trigger.
def test_white_noise_no_trigger():
    vad = VoiceVAD()
    rng = np.random.default_rng(42)
    signal = rng.normal(0, 500, SR * 3).astype(np.int16)
    assert not any(_feed(vad, signal))


# Row 3: strong low-frequency rumble (<300Hz, fan-like) must not trigger.
def test_low_freq_rumble_no_trigger():
    vad = VoiceVAD()
    signal = np.concatenate([_ambient(), _tone(80, 1.5, amp=5000)])
    assert not any(_feed(vad, signal))


# Row 4: sub-min_speech_ms bursts must not trigger (persistence gate).
def test_short_pulse_no_trigger():
    vad = VoiceVAD()
    gap = _ambient(0.3, seed=11)
    signal = np.concatenate([_ambient(), _tone(440, 0.06, amp=4000),
                             gap, _tone(440, 0.06, amp=4000), gap,
                             _tone(440, 0.06, amp=4000)])
    assert not any(_feed(vad, signal))


# Row 5: sustained speech must not fatten the EMA noise floor.
def test_ema_floor_not_fattened_by_speech():
    vad = VoiceVAD()
    ambient = _ambient(1.0)
    speech = _tone(440, 1.0, amp=4000)
    states = _feed(vad, np.concatenate([ambient, speech]))
    assert any(states), "precondition: speech segment must trigger"
    speech_band_rms = max(
        vad._band_rms(speech[s:s + vad.frame_size].astype(np.float64))
        for s in range(0, len(speech) - vad.frame_size, vad.hop_size))
    assert vad.noise_floor < 0.5 * speech_band_rms


# Floor must stay pinned to the ambient level across a full speech episode.
def test_floor_tracks_ambient_then_survives_speech():
    vad = VoiceVAD()
    _feed(vad, _ambient(1.0))
    floor_quiet = vad.noise_floor
    assert floor_quiet > 0
    _feed(vad, _tone(440, 0.8, amp=4000))
    assert abs(vad.noise_floor - floor_quiet) <= 0.25 * floor_quiet


# Cold-start poisoning must be recoverable: an utterance that begins before
# any ambient was seen (bootstrap eats it) must not brick later detections.
def test_recovery_after_cold_start_poisoning():
    vad = VoiceVAD()
    first = _tone(440, 1.0, amp=4000)          # starts at t=0: floor poisoned
    assert not any(_feed(vad, first))
    silence = _ambient(1.5, seed=3, level=30)  # gated EMA pulls floor down
    _feed(vad, silence)
    second = np.concatenate([silence[-CHUNK:], _tone(660, 0.8, amp=4000)])
    assert any(_feed(vad, second)), "second utterance after calm must trigger"


# ESP32 corpus behavioral gate: clean-lead pos files trigger, neg files don't.
POS_TRIGGER = ["pos_heymiaomiao.wav", "pos_heymiaomiao_n.wav"]
NEG_SILENT = ["neg_noise_mid.wav", "neg_noise_quiet.wav"]


def _load_wav(path):
    with wave.open(path) as w:
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16)
    if rate != SR:
        n = int(len(samples) * SR / rate)
        samples = np.interp(np.linspace(0, len(samples) - 1, n),
                            np.arange(len(samples)), samples)
    return samples.astype(np.int16)


def _fixture_triggers(name):
    vad = VoiceVAD()
    return any(_feed(vad, _load_wav(os.path.join(FIXTURES, name))))


def test_fixture_pos_corpus_triggers():
    for name in POS_TRIGGER:
        assert _fixture_triggers(name), f"{name} failed to trigger"


def test_fixture_neg_corpus_stays_silent():
    for name in NEG_SILENT:
        assert not _fixture_triggers(name), f"{name} falsely triggered"


def test_fixture_burst_discrimination_stats():
    """Numeric evidence for the band-separation premise (PLAN-3c §1).

    Whole-file medians are diluted by silence padding; the discriminative
    structure is burst peaks vs steady noise, so compare per-file p90.
    """
    p90s = {}
    for name in POS_TRIGGER + NEG_SILENT + ["pos_heymiaomiao_alt.wav",
                                            "pos_heymiaomiao_s.wav"]:
        x = _load_wav(os.path.join(FIXTURES, name)).astype(np.float64)
        vad = VoiceVAD()
        rms = [vad._band_rms(x[s:s + vad.frame_size])
               for s in range(0, len(x) - vad.frame_size, vad.hop_size)]
        p90s[name] = float(np.percentile(rms, 90))
    pos_p90_min = min(p90s[f] for f in ["pos_heymiaomiao.wav", "pos_heymiaomiao_n.wav"])
    neg_p90_max = max(p90s[f] for f in NEG_SILENT)
    print(f"\nburst discrimination pos_p90_min={pos_p90_min:.0f} "
          f"neg_p90_max={neg_p90_max:.0f} ratio={pos_p90_min / neg_p90_max:.1f}x")
    assert pos_p90_min > neg_p90_max, "corpus lost burst-vs-noise separation"
