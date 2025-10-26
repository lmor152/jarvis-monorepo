from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pveagle  # type: ignore

LOGGER = logging.getLogger(__name__)


class EagleRecogniser:
    """Wrapper around Picovoice Eagle for lightweight speaker identification."""

    def __init__(
        self,
        *,
        access_key: str,
        voices_dir: Path,
        min_score: float = 0.75,
        smoothing: float = 0.4,
        silence_decay: float = 0.95,
    ) -> None:
        if not access_key:
            raise ValueError("Picovoice access key is required for Eagle recognition")

        self._voices_dir = Path(voices_dir)
        if not self._voices_dir.is_dir():
            raise FileNotFoundError(f"Voices directory not found: {self._voices_dir}")

        profile_paths = sorted(p for p in self._voices_dir.iterdir() if p.is_file())
        if not profile_paths:
            raise ValueError(f"No Eagle voice profiles found in {self._voices_dir}")

        self._profile_bytes: List[bytes] = [path.read_bytes() for path in profile_paths]
        self._labels: List[str] = [path.stem for path in profile_paths]

        profiles = [
            pveagle.EagleProfile.from_bytes(data) for data in self._profile_bytes
        ]

        try:
            self._recogniser = pveagle.create_recognizer(
                access_key=access_key,
                speaker_profiles=profiles,
            )
        except pveagle.EagleError as exc:  # type: ignore[attr-defined]
            raise RuntimeError(f"Failed to initialise Eagle recogniser: {exc}") from exc

        self.sample_rate: int = int(self._recogniser.sample_rate)
        self.frame_length: int = int(self._recogniser.frame_length)

        # Clamp tuning parameters to sensible ranges.
        self._min_score: float = float(min(max(min_score, 0.0), 1.0))
        self._release_score: float = max(
            0.0, min(self._min_score - 0.05, self._min_score * 0.7)
        )
        self._alpha: float = float(min(max(smoothing, 0.05), 0.95))
        self._silence_decay: float = float(min(max(silence_decay, 0.0), 0.999))

        self._scores: Dict[str, float] = {label: 0.0 for label in self._labels}
        self._totals: Dict[str, float] = {label: 0.0 for label in self._labels}
        self._pcm_buffer: List[int] = []

        self._current_label: Optional[str] = None
        self._current_score: float = 0.0
        self._peak_label: Optional[str] = None
        self._peak_score: float = 0.0

        LOGGER.debug("Eagle recogniser ready for profiles: %s", ", ".join(self._labels))

    @property
    def labels(self) -> Tuple[str, ...]:
        return tuple(self._labels)

    @property
    def min_score(self) -> float:
        return self._min_score

    def process(
        self,
        pcm: np.ndarray | Sequence[int],
        *,
        voice_detected: bool,
    ) -> Tuple[Optional[str], float]:
        """Feed audio into the recogniser and return the active speaker, if any."""

        frame = self._coerce_frame(pcm)
        if frame:
            self._pcm_buffer.extend(frame)

        if not voice_detected:
            self._pcm_buffer.clear()
            self._decay_scores(self._silence_decay)
            self._update_current_from_scores()
            return self._current_label, self._current_score

        while len(self._pcm_buffer) >= self.frame_length:
            chunk = self._pcm_buffer[: self.frame_length]
            del self._pcm_buffer[: self.frame_length]
            scores = self._recogniser.process(chunk)
            self._apply_scores(scores)

        self._update_current_from_scores()
        return self._current_label, self._current_score

    def best_match(self) -> Tuple[Optional[str], float]:
        """Return the best speaker observed in the current session."""

        if self._current_label and self._current_score >= self._min_score:
            return self._current_label, self._current_score
        if self._peak_label and self._peak_score >= self._min_score:
            return self._peak_label, self._peak_score
        return None, 0.0

    def reset(self) -> None:
        """Clear accumulated state for a fresh listening run."""

        self._pcm_buffer.clear()
        for label in self._scores:
            self._scores[label] = 0.0
        for label in self._totals:
            self._totals[label] = 0.0
        self._current_label = None
        self._current_score = 0.0
        self._peak_label = None
        self._peak_score = 0.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _coerce_frame(self, pcm: np.ndarray | Sequence[int]) -> List[int]:
        if isinstance(pcm, np.ndarray):
            return pcm.astype(np.int16).tolist()
        return [int(sample) for sample in pcm]

    def _apply_scores(self, scores: Iterable[float]) -> None:
        for label, raw_score in zip(self._labels, scores):
            previous = self._scores[label]
            updated = previous * (1.0 - self._alpha) + float(raw_score) * self._alpha
            self._scores[label] = updated
            total_prev = self._totals[label]
            self._totals[label] = total_prev * (1.0 - self._alpha) + float(raw_score)

    def _decay_scores(self, factor: float) -> None:
        if factor <= 0.0:
            for label in self._scores:
                self._scores[label] = 0.0
            return

        for label in self._scores:
            self._scores[label] *= factor

    def _update_current_from_scores(self) -> None:
        if not self._scores:
            self._current_label = None
            self._current_score = 0.0
            return

        totals_sum = sum(self._totals.values())
        if totals_sum > 0.0:
            score_source: Dict[str, float] = self._totals
            total_sum = totals_sum
        else:
            total_sum = sum(self._scores.values())
            if total_sum <= 0.0:
                self._current_label = None
                self._current_score = 0.0
                return
            score_source = self._scores

        best_label, best_value = max(score_source.items(), key=lambda item: item[1])
        confidence = float(best_value) / float(total_sum) if total_sum else 0.0

        if confidence > self._peak_score:
            self._peak_score = confidence
            self._peak_label = best_label

        if confidence >= self._min_score:
            self._current_label = best_label
            self._current_score = confidence
            return

        if self._current_label == best_label:
            self._current_score = confidence
            return

        if self._current_label is None:
            self._current_score = confidence
            self._current_label = best_label if confidence > 0.0 else None
            return

        if self._current_score < self._release_score:
            self._current_label = None
            self._current_score = 0.0
        else:
            self._current_score *= self._silence_decay
