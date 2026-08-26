"""Worker re-arm state machine unit tests (PLAN-3d Phase 2).

Tests the lockout + L1 release + cap logic with monkeypatched ASR.
"""

import time

import pytest

from mycat.voice_assistant.voice_worker import VoiceWorker


def test_rearm_lockout_basic(qapp, monkeypatch, tmp_path):
    """After intent emit, re-arm enters lockout and blocks re-trigger."""
    import yaml

    from mycat.voice_assistant.voice_worker import VoiceWorker
    from mycat.voice_assistant.core.asr_pipeline import ASRPipeline

    # Mock ASR to return a fixed transcription immediately
    original_transcribe = ASRPipeline.transcribe

    def mock_transcribe(self, audio_np):
        return "hello"

    monkeypatch.setattr(ASRPipeline, "transcribe", mock_transcribe)

    with open("tests/fixtures/config_test.yaml") as f:
        cfg = yaml.safe_load(f)

    # Use a short lockout for testing
    cfg["vad"]["retrigger_lockout_ms"] = 100
    cfg["vad"]["rearm_max_wait_ms"] = 5000
    test_cfg = tmp_path / "test_config.yaml"
    test_cfg.write_text(yaml.safe_dump(cfg))

    worker = VoiceWorker(config_path=str(test_cfg))
    events = {"intents": [], "asr_status": []}
    worker.intent_detected_signal.connect(events["intents"].append)
    worker.asr_status_signal.connect(events["asr_status"].append)
    worker.start()

    try:
        # Wait for ASR_READY
        deadline = time.time() + 60
        while time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.05)
            if "ASR_READY" in events["asr_status"]:
                break
        assert "ASR_READY" in events["asr_status"]

        # Let the WAV fixture play (pos_heymiaomiao_n.wav is ~1s)
        # We need to wait for the intent to be emitted
        deadline = time.time() + 10
        while time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.05)
            if events["intents"]:
                break

        # Should have exactly 1 CHAT intent
        chats = [i for i in events["intents"] if i.get("type") == "CHAT"]
        assert len(chats) == 1, f"expected 1 CHAT, got {len(chats)}: {events['intents']}"

        # Verify re-arm state
        assert worker._rearming is True
        assert worker._last_trigger_time > 0

    finally:
        worker.stop()


def test_rearm_pure_L0_path(qapp, monkeypatch, tmp_path):
    """Pure L0 mode (no voice: section) still applies lockout."""
    import yaml

    from mycat.voice_assistant.voice_worker import VoiceWorker
    from mycat.voice_assistant.core.asr_pipeline import ASRPipeline

    original_transcribe = ASRPipeline.transcribe

    def mock_transcribe(self, audio_np):
        return "hello"

    monkeypatch.setattr(ASRPipeline, "transcribe", mock_transcribe)

    with open("tests/fixtures/config_test.yaml") as f:
        cfg = yaml.safe_load(f)
    # Remove voice section = pure L0
    del cfg["vad"]["voice"]
    cfg["vad"]["retrigger_lockout_ms"] = 100
    cfg["vad"]["rearm_max_wait_ms"] = 5000
    test_cfg = tmp_path / "test_config_l0.yaml"
    test_cfg.write_text(yaml.safe_dump(cfg))

    worker = VoiceWorker(config_path=str(test_cfg))
    events = {"intents": [], "asr_status": []}
    worker.intent_detected_signal.connect(events["intents"].append)
    worker.asr_status_signal.connect(events["asr_status"].append)
    worker.start()

    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.05)
            if "ASR_READY" in events["asr_status"]:
                break
        assert "ASR_READY" in events["asr_status"]

        deadline = time.time() + 10
        while time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.05)
            if events["intents"]:
                break

        chats = [i for i in events["intents"] if i.get("type") == "CHAT"]
        assert len(chats) == 1, f"expected 1 CHAT in pure L0, got {len(chats)}"

    finally:
        worker.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])