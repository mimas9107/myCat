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

import pytest

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


def test_worker_voice_vad_wiring(qapp, tmp_path):
    """PLAN-3c Phase 2: voice: section wires Layer 1; absent section = pure L0."""
    import yaml

    from mycat.voice_assistant.voice_worker import VoiceWorker

    with open(TEST_CONFIG) as f:
        cfg = yaml.safe_load(f)
    assert "voice" in cfg["vad"], "config_test.yaml must carry the voice section"
    del cfg["vad"]["voice"]
    legacy_path = tmp_path / "config_no_voice.yaml"
    legacy_path.write_text(yaml.safe_dump(cfg))

    w_on = VoiceWorker(config_path=TEST_CONFIG)
    try:
        assert w_on.voice_vad is not None
        assert w_on._voice_vad_active is True
        assert w_on.voice_vad.snr_on == 2.25
        assert w_on.vad.threshold == 2000.0  # L0 untouched by the voice section
    finally:
        w_on.deleteLater()

    w_off = VoiceWorker(config_path=str(legacy_path))
    try:
        assert w_off.voice_vad is None
        assert w_off._voice_vad_active is False  # exact legacy behavior path
    finally:
        w_off.deleteLater()


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


# ── TASK-3c Phase 3: remaining clean-lead fixtures through the full pipeline ──
#
# pos_alt/pos_s are excluded here: both start mid-speech at t=0, so the
# adaptive bootstrap eats their only utterance (documented cold-start limit,
# covered by the recovery unit test in test_voice_vad.py).

CLEAN_LEAD_POS = ["pos_heymiaomiao_n.wav"]
CLEAN_LEAD_NEG = ["neg_noise_quiet.wav"]
PLAYOUT_SEC = 8.0  # 3s fixture + transcription margin after ASR_READY


def _run_real_pipeline(qapp, monkeypatch, fixture):
    from mycat.voice_assistant.voice_worker import VoiceWorker

    monkeypatch.setenv("MYCAT_AUDIO_WAV", os.path.join(FIXTURES, fixture))
    worker = VoiceWorker(config_path=TEST_CONFIG)
    events = {"intents": [], "asr_status": []}
    worker.intent_detected_signal.connect(events["intents"].append)
    worker.asr_status_signal.connect(events["asr_status"].append)
    worker.start()
    try:
        ready_at = None
        deadline = time.time() + 120
        while time.time() < deadline and qapp is not None:
            qapp.processEvents()
            time.sleep(0.05)
            if ready_at is None and "ASR_READY" in events["asr_status"]:
                ready_at = time.time()
            elif ready_at is not None:
                if any(i.get("type") == "CHAT" for i in events["intents"]):
                    break
                if time.time() - ready_at >= PLAYOUT_SEC:
                    break
        assert ready_at is not None, f"{fixture}: warm-start failed: {events['asr_status']}"
    finally:
        worker.stop()
    return events


@pytest.mark.parametrize("fixture", CLEAN_LEAD_POS)
def test_clean_lead_pos_fixture_reaches_intent(qapp, monkeypatch, fixture):
    events = _run_real_pipeline(qapp, monkeypatch, fixture)
    chats = [i for i in events["intents"] if i.get("type") == "CHAT"]
    assert chats, f"{fixture} produced no intent; asr={events['asr_status']}"


@pytest.mark.parametrize("fixture", CLEAN_LEAD_NEG)
def test_clean_lead_neg_fixture_stays_silent(qapp, monkeypatch, fixture):
    events = _run_real_pipeline(qapp, monkeypatch, fixture)
    assert events["intents"] == [], f"{fixture} falsely triggered: {events['intents']}"


# ── TASK-3c Phase 3: user-recorded validation corpus (INMP441-spec re-records) ──
#
# Acceptance trio from PLAN-3c §4: fan must not trigger, knock must not
# trigger (transient rejection through the persistence gate), distant
# speech must trigger.

USER_REC_POS = ["heymiaomiao.wav"]           # distant speech → CHAT
USER_REC_NEG = ["fan.wav", "knockknock.wav"]  # steady noise / impulse → silence


@pytest.mark.parametrize("fixture", USER_REC_POS)
def test_user_recording_distant_speech_reaches_intent(qapp, monkeypatch, fixture):
    events = _run_real_pipeline(qapp, monkeypatch, fixture)
    chats = [i for i in events["intents"] if i.get("type") == "CHAT"]
    assert chats, f"distant speech '{fixture}' not detected; asr={events['asr_status']}"


@pytest.mark.parametrize("fixture", USER_REC_NEG)
def test_user_recording_nonvoice_stays_silent(qapp, monkeypatch, fixture):
    events = _run_real_pipeline(qapp, monkeypatch, fixture)
    assert events["intents"] == [], f"'{fixture}' falsely triggered: {events['intents']}"
