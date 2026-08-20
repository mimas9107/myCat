"""End-to-end pipeline test: WAV → ASR → Intent → Ollama → response."""
import sys, time, wave, struct, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def load_wav_mono(path):
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
    if sw != 2:
        raise ValueError(f"expected 16-bit, got {sw*8}-bit")
    samples = list(struct.unpack(f"<{n * ch}h", raw))
    if ch > 1:
        samples = [samples[i] for i in range(0, len(samples), ch)]
    import numpy as np
    return np.array(samples, dtype=np.float32), sr

def main():
    wav_path = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/sounds/alsa/Front_Center.wav"
    print(f"=== E2E Pipeline Test ===")
    print(f"WAV: {wav_path}\n")

    # 1. ASR
    from mycat.voice_assistant.core.asr_pipeline import ASRPipeline
    asr = ASRPipeline(model_size="base", device="cpu", compute_type="int8", language="en")
    audio, sr = load_wav_mono(wav_path)
    # Resample to 16kHz if needed
    if sr != 16000:
        import numpy as np
        ratio = 16000 / sr
        new_len = int(len(audio) * ratio)
        audio = np.interp(np.linspace(0, len(audio), new_len, endpoint=False), np.arange(len(audio)), audio).astype(np.float32)
        sr = 16000
        print(f"[1] Audio loaded: {len(audio)} samples ({len(audio)/sr:.1f}s), resampled to {sr}Hz")
    else:
        print(f"[1] Audio loaded: {len(audio)} samples ({len(audio)/sr:.1f}s), SR={sr}")

    t0 = time.time()
    text = asr.transcribe(audio)
    dt = time.time() - t0
    print(f"[2] ASR result ({dt:.1f}s): '{text}'")

    # 2. Intent
    from mycat.voice_assistant.core.intent_parser import parse_text_to_intent
    intent = parse_text_to_intent(text)
    print(f"[3] Intent: {intent['type']}  data={intent['data']}")

    # 3. Ollama
    if intent["type"] == "CHAT" and text:
        from mycat.llm_ollama import OllamaBackend
        backend = OllamaBackend(url="http://localhost:11434", model="tinyllama:latest", timeout=30)
        print(f"[4] Calling Ollama (tinyllama)...")
        t0 = time.time()
        reply = backend.reply(text, "You are a cute cat. Reply briefly and playfully.")
        dt = time.time() - t0
        print(f"[5] Ollama reply ({dt:.1f}s): '{reply}'")
    else:
        print(f"[4] Skipped Ollama (intent={intent['type']})")

    print("\n=== Pipeline complete ===")

if __name__ == "__main__":
    main()
