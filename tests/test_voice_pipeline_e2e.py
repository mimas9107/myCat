"""Voice pipeline E2E — real components, WAV-fixture audio source.

Three layers, per PLAN-3b:
1. Intent parser unit tests (pure regex, no hardware).
2. SLEEP → animation state-machine wiring (no audio; handle_intent called directly).
3. Full pipeline: VoiceWorker with MYCAT_AUDIO_WAV feeding a fixture through the
   real WavAudioStream → EnergyVAD → ASRPipeline chain.  Only the microphone and
   the Ollama HTTP boundary are stand-ins; VAD/ASR/intent run for real.

VAD threshold comes from tests/fixtures/config_test.yaml, calibrated for the
ESP32 fixture recordings (production's 21000 targets the desktop mic gain).
"""

import os
import time

from mycat.voice_assistant.core.intent_parser import parse_text_to_intent

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "audio")
TEST_CONFIG = os.path.join(os.path.dirname(__file__), "fixtures", "config_test.yaml")


# ── Layer 1: intent parser ────────────────────────────────────────


def test_intent_parser_sleep_paths():
    for phrase in ("go to sleep", "sleep", "hide", "rest", "shut down", "turn off"):
        assert parse_text_to_intent(phrase)["type"] == "SLEEP", phrase
    # word-boundary guard: "rest" inside another word must not match
    assert parse_text_to_intent("interesting facts")["type"] == "CHAT"


def test_intent_parser_set_reminder():
    intent = parse_text_to_intent("remind me to stretch")
    assert intent["type"] == "SET_REMINDER"
    assert "stretch" in intent["data"]["message"]


def test_intent_parser_chat_fallback_and_none():
    assert parse_text_to_intent("hey miaomiao")["type"] == "CHAT"
    assert parse_text_to_intent("")["type"] == "NONE"


# ── Layer 2: SLEEP → animation wiring (no audio needed) ──────────


class _FakePack:
    def __init__(self, sleep_in=None, sleep=None):
        self.sleep_in = sleep_in
        self.sleep = sleep
        self.static = object()


class _FakeWindow:
    def __init__(self, char_pack=None):
        self.char_pack = char_pack
        self.base_state = "idle"
        self.current_pixmap = None
        self.closed = False
        self.clips = []

    def pack_now(self):
        return object()

    def start_clip(self, clip, state, now):
        self.clips.append((clip, state))

    def update(self):
        pass

    def close(self):
        self.closed = True


def _bare_bridge(window):
    """VoiceBridge skeleton with only .window wired — for method-level tests."""
    from mycat.voice_bridge import VoiceBridge

    bridge = VoiceBridge.__new__(VoiceBridge)
    bridge.window = window
    bridge._sleep_callback = None
    bridge._reminder_callback = None
    bridge._llm_backend = None
    bridge._chat_thread = None
    return bridge


def test_sleep_without_callback_closes_window(qapp):
    win = _FakeWindow()
    assert _bare_bridge(win).handle_intent("SLEEP", {}) is True
    assert win.closed


def test_sleep_callback_invoked_and_window_kept(qapp):
    win = _FakeWindow()
    bridge = _bare_bridge(win)
    calls = []
    bridge.set_sleep_callback(lambda: calls.append(1))
    assert bridge.handle_intent("SLEEP", {}) is True
    assert calls and not win.closed


def test_reminder_callback_invoked(qapp):
    bridge = _bare_bridge(_FakeWindow())
    calls = []
    bridge.set_reminder_callback(lambda: calls.append(1))
    assert bridge.handle_intent("SET_REMINDER", {}) is True
    assert calls


def test_sleep_animation_uses_sleep_in_clip(qapp):
    pack = _FakePack(sleep_in=object())
    win = _FakeWindow(char_pack=pack)
    _bare_bridge(win)._window_sleep_animation()
    assert len(win.clips) == 1 and win.clips[0][1] == "sleeping"


def test_sleep_animation_falls_back_to_static_frame(qapp):
    pack = _FakePack(sleep=object())  # no sleep_in clip material
    win = _FakeWindow(char_pack=pack)
    _bare_bridge(win)._window_sleep_animation()
    assert win.base_state == "sleeping"
    assert win.current_pixmap is pack.sleep


def test_sleep_animation_without_material_closes_window(qapp):
    win = _FakeWindow(char_pack=None)
    _bare_bridge(win)._window_sleep_animation()
    assert win.closed


# ── Layer 3: full pipeline E2E (real VAD + ASR, WAV source) ──────


def _drain(qapp, seconds):
    end = time.time() + seconds
    while time.time() < end:
        qapp.processEvents()
        time.sleep(0.05)


def test_wav_fixture_reaches_intent_through_real_pipeline(qapp):
    from mycat.voice_assistant.voice_worker import VoiceWorker

    worker = VoiceWorker(config_path=TEST_CONFIG)
    events = {"status": [], "intents": [], "asr_status": []}
    worker.status_changed_signal.connect(events["status"].append)
    worker.intent_detected_signal.connect(events["intents"].append)
    worker.asr_status_signal.connect(events["asr_status"].append)
    worker.start()
    try:
        deadline = time.time() + 120  # generous: whisper base load on slow CPUs
        while time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.05)
            if any(i.get("type") == "CHAT" for i in events["intents"]):
                break

        assert "ASR_READY" in events["asr_status"], f"warm-start failed: {events['asr_status']}"
        chats = [i for i in events["intents"] if i.get("type") == "CHAT"]
        assert chats, f"speech fixture produced no intent; statuses={events['status']}, asr={events['asr_status']}"
        text = chats[0]["data"].get("text", "")
        assert text.strip(), "ASR returned empty transcription"
    finally:
        worker.stop()


def test_noise_fixture_produces_no_intent(qapp, monkeypatch):
    from mycat.voice_assistant.voice_worker import VoiceWorker

    monkeypatch.setenv("MYCAT_AUDIO_WAV", os.path.join(FIXTURES, "neg_noise_mid.wav"))
    worker = VoiceWorker(config_path=TEST_CONFIG)
    events = {"status": [], "intents": [], "asr_status": []}
    worker.status_changed_signal.connect(events["status"].append)
    worker.intent_detected_signal.connect(events["intents"].append)
    worker.asr_status_signal.connect(events["asr_status"].append)
    worker.start()
    try:
        # wait for warm-start, then let the 3s noise file play out fully
        deadline = time.time() + 120
        while time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.05)
            if "ASR_READY" in events["asr_status"]:
                break
        assert "ASR_READY" in events["asr_status"], f"warm-start failed: {events['asr_status']}"
        _drain(qapp, 5.0)
        assert events["intents"] == [], f"noise falsely triggered: {events['intents']}"
    finally:
        worker.stop()
