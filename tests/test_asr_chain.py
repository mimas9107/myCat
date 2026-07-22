#!/usr/bin/env python3
"""Synthetic audio test — feeds known audio through ASR pipeline to verify data chain.

Usage:
    python3 tests/test_asr_chain.py                  # generate sine wave (no speech)
    python3 tests/test_asr_chain.py hello.wav        # feed a WAV file
    python3 tests/test_asr_chain.py --speak "hello"  # generate speech-like audio

Tests the full chain: audio → ASR → intent parser.
"""

import sys
import os
import time
import wave
import struct

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_tone(freq=440, duration_s=2.0, sample_rate=16000):
    """Generate a simple sine wave (simulates non-speech audio)."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), dtype=np.float32)
    samples = (np.sin(2 * np.pi * freq * t) * 5000).astype(np.int16)
    return samples


def load_wav_file(path):
    """Load a WAV file and return int16 samples at target sample rate."""
    with wave.open(path, 'rb') as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.int16)
    elif sampwidth == 4:
        samples = np.frombuffer(raw, dtype=np.int32)
        samples = (samples / 65536).astype(np.int16)
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    # Mix to mono if stereo
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)

    # Resample if needed
    if framerate != 16000:
        ratio = 16000 / framerate
        new_len = int(len(samples) * ratio)
        samples = np.interp(
            np.linspace(0, len(samples) - 1, new_len),
            np.arange(len(samples)),
            samples.astype(np.float64),
        ).astype(np.int16)

    return samples


def main():
    print("=" * 60)
    print("ASR Chain Test — Verify data pipeline without speaking")
    print("=" * 60)

    # Prepare audio
    if len(sys.argv) > 1 and sys.argv[1] == "--speak":
        # Generate speech-like audio (multiple harmonics)
        print("\n[1] Generating speech-like audio (2s)...")
        duration = 2.0
        sr = 16000
        t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
        # Simulate formants: F0=120Hz + harmonics (roughly male voice)
        audio = np.zeros_like(t)
        for freq in [120, 240, 480, 2400, 3200]:
            audio += np.sin(2 * np.pi * freq * t) * (5000 / freq)
        audio = (audio * 5000).astype(np.int16)
        expected_text = "(synthetic tone — ASR may return empty or garbled)"
    elif len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        # Load WAV file
        print(f"\n[1] Loading WAV: {sys.argv[1]}")
        audio = load_wav_file(sys.argv[1])
        expected_text = "(known content from WAV file)"
    else:
        # Default: sine wave
        print("\n[1] Generating 440Hz sine wave (2s)...")
        audio = generate_tone(440, 2.0)
        expected_text = "(pure sine — ASR should return empty)"

    print(f"    Audio: {len(audio)} samples ({len(audio)/16000:.1f}s)")
    print(f"    RMS:   {np.sqrt(np.mean(audio.astype(np.float64)**2)):.0f}")

    # Run ASR
    print("\n[2] Loading ASR model...")
    from mycat.voice_assistant.core.asr_pipeline import ASRPipeline
    asr = ASRPipeline(model_size="base", device="cpu", compute_type="int8", language="en")

    print("[3] Transcribing...")
    start = time.time()
    result = asr.transcribe(audio)
    elapsed = time.time() - start

    print(f"    Result: '{result}'")
    print(f"    Time:   {elapsed:.1f}s")

    # Run intent parser
    print("\n[4] Intent parsing...")
    from mycat.voice_assistant.core.intent_parser import parse_text_to_intent
    intent = parse_text_to_intent(result)
    print(f"    Intent: {intent['type']}")
    if intent['data']:
        print(f"    Data:   {intent['data']}")

    # Summary
    print("\n" + "=" * 60)
    if result:
        print(f"ASR returned: '{result}'")
        print("Pipeline FULLY WORKING: audio → ASR → text → intent")
    else:
        print("ASR returned empty (expected for non-speech audio)")
        print("Pipeline PARTIALLY WORKING: audio → ASR → empty (no speech detected)")
    print("=" * 60)


if __name__ == "__main__":
    main()
