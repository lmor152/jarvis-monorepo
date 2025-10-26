from __future__ import annotations

from typing import Any, Sequence, cast

import numpy as np
import pvcobra  # type: ignore


class CobraVAD:
    """Thin wrapper around Picovoice Cobra providing boolean voice activity."""

    def __init__(self, access_key: str, threshold: float = 0.2):
        self.cobra: Any = pvcobra.create(access_key=access_key)  # type: ignore[attr-defined]
        self.threshold = threshold
        self.frame_length = int(cast(int, self.cobra.frame_length))  # type: ignore[misc]
        self.sample_rate = int(cast(int, self.cobra.sample_rate))  # type: ignore[misc]

    def process(self, pcm: np.ndarray | Sequence[int]) -> float:
        """Return Cobra's voice probability for a PCM frame."""
        if isinstance(pcm, np.ndarray):
            frame = pcm.astype(np.int16).tolist()
        else:
            frame = list(pcm)

        if len(frame) != self.frame_length:
            raise ValueError(
                f"Expected frame of {self.frame_length} samples, received {len(frame)}"
            )

        return float(self.cobra.process(frame))

    def is_speech(self, pcm: np.ndarray | Sequence[int]) -> bool:
        return self.process(pcm) >= self.threshold

    def reset(self) -> None:
        try:
            self.cobra.reset()
        except AttributeError:
            # Older Cobra builds may not expose reset; ignore if unavailable.
            pass

    def delete(self) -> None:
        self.cobra.delete()
