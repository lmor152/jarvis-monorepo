from __future__ import annotations

import io
import math
import wave
from array import array
from typing import Any, Sequence

import numpy as np
from openai import OpenAI


class OpenAIWhisperSTT:
    """Streaming-ish STT that defers recognition to OpenAI Whisper models."""

    def __init__(
        self,
        api_key: str | None,
        sample_rate: int,
        endpoint_silence_ms: int = 900,
        min_energy: float = 60.0,
        model: str = "gpt-4o-mini-transcribe",
    ) -> None:
        self.sample_rate = sample_rate
        self.endpoint_silence_ms = endpoint_silence_ms
        self.min_energy = min_energy
        self.model = model
        self.client = OpenAI(api_key=api_key)

        self.buffer = array("h")
        self.frame_length: int | None = None
        self.frame_duration_ms: float = 0.0
        self.endpoint_silence_frames: int = 0
        self.silence_frames = 0
        self.has_voice = False

    def process(self, pcm: np.ndarray | Sequence[int]) -> tuple[str, bool]:
        frame = self._ensure_np_int16(pcm)

        if self.frame_length is None:
            self.frame_length = len(frame)
            if self.frame_length == 0:
                return "", False
            self.frame_duration_ms = 1000.0 * self.frame_length / self.sample_rate
            self.endpoint_silence_frames = max(
                1, int(math.ceil(self.endpoint_silence_ms / self.frame_duration_ms))
            )

        self.buffer.extend(frame.tolist())

        energy = float(np.mean(np.abs(frame)))
        if energy >= self.min_energy:
            self.silence_frames = 0
            self.has_voice = True
        else:
            self.silence_frames += 1

        if (
            self.has_voice
            and self.endpoint_silence_frames
            and self.silence_frames >= self.endpoint_silence_frames
        ):
            transcript = self._transcribe_buffer()
            return transcript, True

        return "", False

    def flush(self) -> str:
        return self._transcribe_buffer()

    def reset(self) -> None:
        self.buffer = array("h")
        self.silence_frames = 0
        self.has_voice = False

    def delete(self) -> None:  # pragma: no cover - nothing to release explicitly
        self.reset()

    # ------------------------------------------------------------------

    def _ensure_np_int16(self, pcm: np.ndarray | Sequence[int]) -> np.ndarray:
        if isinstance(pcm, np.ndarray):
            return pcm.astype(np.int16, copy=False)
        return np.asarray(pcm, dtype=np.int16)

    def _transcribe_buffer(self) -> str:
        if not self.buffer:
            return ""

        audio_bytes = self.buffer.tobytes()
        self.buffer = array("h")
        self.silence_frames = 0
        self.has_voice = False

        wav_stream = self._wrap_wav(audio_bytes)

        try:
            response: Any = self.client.audio.transcriptions.create(
                model=self.model,
                file=("speech.wav", wav_stream, "audio/wav"),
            )
            text = getattr(response, "text", "") or ""
            return text.strip()
        except Exception as exc:  # pragma: no cover - depends on network
            print(f"OpenAI STT error: {exc}")
            return ""

    def _wrap_wav(self, pcm_bytes: bytes) -> io.BytesIO:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm_bytes)
        buffer.seek(0)
        return buffer
