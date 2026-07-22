#!/usr/bin/env python3
"""Standalone VAD tester — listens to mic and prints energy levels in real-time.

Usage:
    python3 tests/test_vad.py              # auto-select first usable mic
    MYCAT_MIC_DEVICE=3 python3 tests/test_vad.py  # force device index

Shows:
- Available audio input devices
- Real-time energy per 100ms chunk
- Rolling average (ambient noise floor)
- Recommended threshold based on observation
- Press Ctrl+C to stop
"""

import collections
import math
import os
import sys
import time

try:
    import pyaudio
except ImportError:
    print("ERROR: PyAudio not installed.")
    print("  sudo apt install portaudio19-dev && pip install pyaudio")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("ERROR: numpy not installed.")
    sys.exit(1)


def list_devices(p):
    """Print all available audio input devices."""
    print("=" * 70)
    print("Available Audio Input Devices:")
    print("=" * 70)
    info = p.get_host_api_info_by_index(0)
    num_devices = info.get("deviceCount")
    for i in range(num_devices):
        try:
            device_info = p.get_device_info_by_host_api_device_index(0, i)
            if device_info.get("maxInputChannels") > 0:
                name = device_info.get("name", "?")
                ch = device_info.get("maxInputChannels")
                rate = device_info.get("defaultSampleRate", "?")
                print(f"  [{i}] {name} | channels={ch} | rate={rate:.0f}Hz")
        except Exception:
            pass
    print("=" * 70)


def calculate_energy(data_bytes):
    """Calculate mean energy from raw PCM int16 bytes."""
    samples = np.frombuffer(data_bytes, dtype=np.int16).astype(np.float64)
    if len(samples) == 0:
        return 0.0
    return float(np.sum(samples ** 2) / len(samples))


def main():
    p = pyaudio.PyAudio()
    list_devices(p)

    # Pick device
    env_dev = os.environ.get("MYCAT_MIC_DEVICE")
    if env_dev is not None:
        device_index = int(env_dev)
    else:
        # Auto-pick: prefer pulse (most stable with PyAudio), then pipewire, skip raw ALSA
        device_index = None
        for i in range(p.get_host_api_info_by_index(0)["deviceCount"]):
            try:
                info = p.get_device_info_by_host_api_device_index(0, i)
                if info.get("maxInputChannels", 0) > 0:
                    name = info.get("name", "").lower()
                    if "pulse" in name:
                        device_index = i
                        break
            except Exception:
                pass
        if device_index is None:
            for i in range(p.get_host_api_info_by_index(0)["deviceCount"]):
                try:
                    info = p.get_device_info_by_host_api_device_index(0, i)
                    if info.get("maxInputChannels", 0) > 0:
                        name = info.get("name", "").lower()
                        if "pipewire" in name:
                            device_index = i
                            break
                except Exception:
                    pass
        if device_index is None:
            print("No virtual audio device found, falling back to first available.")
            device_index = 0

    print(f"\nSelected device [{device_index}]: ", end="", flush=True)
    try:
        dev_info = p.get_device_info_by_host_api_device_index(0, device_index)
        print(dev_info.get("name"))
    except Exception as e:
        print(f"(error: {e})")

    # Try sample rates in priority order
    for target_rate in [16000, 48000, 44100]:
        CHUNK = int(target_rate * 0.1)  # 100ms chunks

        try:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=target_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK,
            )
        except Exception as e:
            if target_rate == 16000:
                print(f"All sample rates failed: {e}")
                p.terminate()
                sys.exit(1)
            continue

        print(f"Stream opened at {target_rate}Hz | Chunk size: {CHUNK} samples\n")
        print(f"{'Time':>7s}  {'Energy':>12s}  {'RMS':>10s}  {'Avg(5s)':>12s}  {'Status':>15s}")
        print("-" * 70)

        energy_history = collections.deque(maxlen=50)  # ~5 seconds at 10Hz
        start_time = time.time()
        last_print = start_time

        try:
            while True:
                data = stream.read(CHUNK, exception_on_overflow=False)
                energy = calculate_energy(data)
                rms = math.sqrt(energy) if energy > 0 else 0

                energy_history.append(energy)
                avg_energy = sum(energy_history) / len(energy_history) if energy_history else 0

                elapsed = time.time() - start_time
                now = time.time()

                # Print every second to avoid spam
                if now - last_print >= 1.0:
                    last_print = now
                    status = ""
                    if avg_energy > 100:
                        ratio = energy / avg_energy if avg_energy > 0 else 1
                        if ratio > 3:
                            status = ">>> SPEECH >>>"
                        elif ratio > 1.5:
                            status = "> rising >"
                    print(f"{elapsed:>7.1f}s  {energy:>12.0f}  {rms:>10.1f}  {avg_energy:>12.0f}  {status:>15s}")

        except KeyboardInterrupt:
            pass
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

            # Summary
            print("\n" + "=" * 70)
            print("Summary:")
            if energy_history:
                energies = list(energy_history)
                avg = sum(energies) / len(energies)
                peak = max(energies)
                # Sort to find median
                sorted_e = sorted(energies)
                median = sorted_e[len(sorted_e) // 2]
                print(f"  Avg energy:    {avg:>12.0f}")
                print(f"  Median energy: {median:>12.0f}  (more stable baseline)")
                print(f"  Peak energy:   {peak:>12.0f}")
                print(f"\n  Recommended thresholds:")
                print(f"    Quiet room:  {int(median * 2):>10d}  (2x median)")
                print(f"    Noisy room:  {int(median * 5):>10d}  (5x median)")
                print(f"    Aggressive:  {int(median * 10):>10d}  (10x median)")
            print("=" * 70)
            break


if __name__ == "__main__":
    main()
