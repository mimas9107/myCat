"""AudioStreamManager clear_buffer() unit tests.

Covers PLAN-3d Phase 1: clear_buffer() thread-safety with feed thread.
"""

import threading
import time

import numpy as np

from mycat.voice_assistant.core.audio_stream import AudioStreamManager


def test_clear_buffer_returns_empty():
    """clear_buffer() empties the ring buffer."""
    mgr = AudioStreamManager(sample_rate=16000, chunk_duration_ms=100, buffer_seconds=1)

    # Feed some audio
    for _ in range(5):
        chunk = np.ones(1600, dtype=np.int16) * 1000
        mgr.ring_buffer.append(chunk)

    assert len(mgr.get_buffered_audio()) > 0

    mgr.clear_buffer()

    assert len(mgr.get_buffered_audio()) == 0
    assert len(mgr.get_recent_chunk(0.1)) == 0


def test_clear_buffer_feed_thread_safety():
    """clear_buffer() + feed thread concurrent access: no deadlock, no exception, new data accumulates."""
    mgr = AudioStreamManager(sample_rate=16000, chunk_duration_ms=100, buffer_seconds=1)

    errors = []
    clear_done = threading.Event()
    feed_done = threading.Event()

    def feed():
        try:
            for i in range(20):
                chunk = np.ones(1600, dtype=np.int16) * (1000 + i)
                with mgr._buffer_lock:
                    mgr.ring_buffer.append(chunk)
                time.sleep(0.005)  # 5ms between chunks
        except Exception as e:
            errors.append(f"feed: {e}")
        finally:
            feed_done.set()

    def clear_loop():
        try:
            for _ in range(10):
                time.sleep(0.01)
                mgr.clear_buffer()
            clear_done.set()
        except Exception as e:
            errors.append(f"clear: {e}")

    t1 = threading.Thread(target=feed, name="feed")
    t2 = threading.Thread(target=clear_loop, name="clear")
    t1.start()
    t2.start()

    t1.join(timeout=5)
    t2.join(timeout=5)

    assert not errors, f"concurrent errors: {errors}"
    assert feed_done.is_set()
    assert clear_done.is_set()

    # After clear loop finishes, feed may have added more chunks
    # Buffer should be usable (no corruption)
    audio = mgr.get_buffered_audio()
    assert isinstance(audio, np.ndarray)


def test_clear_buffer_new_data_accumulates():
    """After clear_buffer(), new feed data continues to accumulate correctly."""
    mgr = AudioStreamManager(sample_rate=16000, chunk_duration_ms=100, buffer_seconds=1)

    # Feed first batch
    for i in range(5):
        chunk = np.ones(1600, dtype=np.int16) * (1000 + i)
        mgr.ring_buffer.append(chunk)
    assert len(mgr.get_buffered_audio()) == 5 * 1600

    # Clear
    mgr.clear_buffer()
    assert len(mgr.get_buffered_audio()) == 0

    # Feed second batch
    for i in range(3):
        chunk = np.ones(1600, dtype=np.int16) * (2000 + i)
        mgr.ring_buffer.append(chunk)
    audio = mgr.get_buffered_audio()
    assert len(audio) == 3 * 1600
    # Audio should contain the three chunks (2000, 2001, 2002)
    assert audio[:1600].mean() == 2000
    assert audio[1600:3200].mean() == 2001
    assert audio[3200:].mean() == 2002


def test_wav_manager_inherits_clear_buffer():
    """WavAudioStreamManager inherits clear_buffer() with identical behavior."""
    import tempfile
    import wave

    from mycat.voice_assistant.core.audio_stream import WavAudioStreamManager

    # Create a dummy WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        # 0.5 seconds of silence
        w.writeframes(b"\x00\x00" * 8000)

    try:
        mgr = WavAudioStreamManager(wav_path, start_delayed=False)
        mgr.start()

        # Wait for some data to be fed
        time.sleep(0.2)

        # Buffer should have data
        assert len(mgr.get_buffered_audio()) > 0

        # Clear
        mgr.clear_buffer()
        assert len(mgr.get_buffered_audio()) == 0

        # Feed thread continues - wait for more data
        time.sleep(0.3)
        # New data should accumulate
        assert len(mgr.get_buffered_audio()) > 0

    finally:
        mgr.stop()
        import os
        os.unlink(wav_path)


if __name__ == "__main__":
    test_clear_buffer_returns_empty()
    print("test_clear_buffer_returns_empty: PASS")
    test_clear_buffer_feed_thread_safety()
    print("test_clear_buffer_feed_thread_safety: PASS")
    test_clear_buffer_new_data_accumulates()
    print("test_clear_buffer_new_data_accumulates: PASS")
    test_wav_manager_inherits_clear_buffer()
    print("test_wav_manager_inherits_clear_buffer: PASS")
    print("\nAll tests passed!")