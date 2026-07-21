import os
import numpy as np


class WakeWordEngine:
    """Edge Impulse Wake Word Engine wrapper."""

    def __init__(self, model_path: str, threshold: float = 0.8):
        self.model_path = model_path
        self.threshold = threshold
        self.runner = None
        self._initialized = False
        self._init_runner()

    def _init_runner(self):
        if not os.path.exists(self.model_path):
            print(
                f"[WakeWordEngine] Warning: Model file {self.model_path} not found. Running in fallback mode."
            )
            return

        try:
            from edge_impulse_linux.audio import AudioImpulseRunner

            self.runner = AudioImpulseRunner(self.model_path)
            model_info = self.runner.init()
            print(
                f"[WakeWordEngine] Loaded Edge Impulse model: {model_info.get('project', {}).get('name', 'Unknown')}"
            )
            self._initialized = True
        except ImportError:
            print(
                "[WakeWordEngine] Warning: edge_impulse_linux SDK not installed. Running in fallback mode."
            )
        except Exception as e:
            print(f"[WakeWordEngine] Error initializing Edge Impulse runner: {e}")

    def predict(self, audio_chunk: np.ndarray) -> tuple[bool, float]:
        """Classifies audio chunk. Returns (is_triggered, confidence_score)."""
        if not self._initialized or self.runner is None:
            # Fallback logic for testing when SDK/model is absent
            return False, 0.0

        try:
            features = audio_chunk.tolist()
            res = self.runner.classify(features)

            scores = res.get("result", {}).get("classification", {})
            max_score = 0.0
            triggered = False
            for label, score in scores.items():
                if score > max_score:
                    max_score = score
                if score >= self.threshold:
                    triggered = True

            return triggered, max_score
        except Exception as e:
            print(f"[WakeWordEngine] Inference error: {e}")
            return False, 0.0

    def stop(self):
        """Stops the Edge Impulse runner."""
        if self.runner:
            try:
                self.runner.stop()
            except Exception:
                pass
            self.runner = None
            self._initialized = False
