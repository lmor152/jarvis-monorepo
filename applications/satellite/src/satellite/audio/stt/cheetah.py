from typing import Sequence

import numpy as np
import pvcheetah  # type: ignore


class CheetahSTT:
    """Streaming speech-to-text using Picovoice Cheetah."""

    def __init__(self, access_key: str):
        self.cheetah = pvcheetah.create(
            access_key=access_key,
            endpoint_duration_sec=1.0,
            enable_automatic_punctuation=True,
        )

    def process(self, pcm: np.ndarray | Sequence[int]) -> tuple[str, bool]:
        """
        Feed PCM frames (int16) to Cheetah and return partial or final transcription.
        Returns a tuple of (transcript, is_endpoint).
        """
        try:
            sequence: Sequence[int]
            if isinstance(pcm, np.ndarray):
                sequence = pcm.tolist()
            else:
                sequence = pcm

            transcript, is_endpoint = self.cheetah.process(sequence)
            return transcript, is_endpoint
        except Exception as e:
            print("STT process error:", e)
            return "", False

    def flush(self):
        """Flush any remaining buffered transcription."""
        try:
            final = self.cheetah.flush()
            return final
        except Exception as e:
            print("STT flush error:", e)
            return None

    def delete(self):
        self.cheetah.delete()

    def reset(self):
        """Flush residual audio so a new session starts clean."""
        try:
            _ = self.cheetah.flush()
        except Exception:
            # Already logged during process/flush; ignore here.
            pass
