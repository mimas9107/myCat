import numpy as np


class ASRPipeline:
    """faster-whisper ASR pipeline wrapper."""

    def __init__(self, model_size="base", device="cpu", compute_type="int8", language="en"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.model = None
        self._initialized = False

    def _ensure_model(self):
        if self._initialized:
            return
        try:
            from faster_whisper import WhisperModel

            print(
                f"[ASRPipeline] Loading faster-whisper model '{self.model_size}'..."
            )
            self.model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
            self._initialized = True
            print("[ASRPipeline] faster-whisper model loaded successfully.")
        except ImportError:
            print(
                "[ASRPipeline] Warning: faster_whisper not installed. Transcribe will return fallback text."
            )
        except Exception as e:
            print(f"[ASRPipeline] Error loading faster-whisper: {e}")

    def transcribe(self, audio_np: np.ndarray) -> str:
        """Transcribes PCM 16-bit 16kHz audio array into text string."""
        self._ensure_model()
        if not self._initialized or self.model is None:
            return ""

        if audio_np is None or len(audio_np) == 0:
            return ""

        try:
            # Convert int16 audio array to float32 normalized [-1.0, 1.0]
            if audio_np.dtype == np.int16:
                audio_float = audio_np.astype(np.float32) / 32768.0
            else:
                audio_float = audio_np.astype(np.float32)

            segments, _info = self.model.transcribe(audio_float, beam_size=5, language=self.language)
            text = "".join(segment.text for segment in segments).strip()
            return text
        except Exception as e:
            print(f"[ASRPipeline] Transcription error: {e}")
            return ""
