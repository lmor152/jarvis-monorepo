import logging
import signal
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Deque, List, cast

import httpx
import numpy as np
import pvporcupine  # type: ignore
import sounddevice as sd  # type: ignore

from satellite.audio.recognition import EagleRecogniser
from satellite.audio.stt.cheetah import CheetahSTT
from satellite.audio.stt.openai import OpenAIWhisperSTT
from satellite.audio.tts.orca import OrcaTTS
from satellite.audio.vad import CobraVAD
from satellite.core.satellite_state import SatelliteState
from satellite.core.settings import settings

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


class VoiceAssistant:
    """
    High-level class combining wakeword, STT, TTS, and state feedback.
    """

    def __init__(self, wake_keyword: str = "jarvis", interrupt_keyword: str = "alexa"):
        self.state = SatelliteState()

        # Wake/interrupt detectors
        wake_provider = settings.wake_provider
        if wake_provider != "picovoice":
            raise ValueError(f"Unsupported wake provider: {wake_provider}")

        wake_keywords = settings.wakewords or [wake_keyword]
        if wake_keyword and wake_keyword not in wake_keywords:
            wake_keywords = [wake_keyword]

        wake_sensitivities = settings.wakeword_sensitivities or [0.5]
        if len(wake_sensitivities) == 1 and len(wake_keywords) > 1:
            wake_sensitivities = wake_sensitivities * len(wake_keywords)
        elif len(wake_sensitivities) < len(wake_keywords):
            wake_sensitivities = (
                wake_sensitivities + [wake_sensitivities[-1]] * len(wake_keywords)
            )[: len(wake_keywords)]
        elif len(wake_sensitivities) > len(wake_keywords):
            wake_sensitivities = wake_sensitivities[: len(wake_keywords)]

        self.wake_keywords = wake_keywords
        self.wake_detector = pvporcupine.create(  # type: ignore[attr-defined]
            keywords=wake_keywords,
            sensitivities=wake_sensitivities,
            access_key=settings.picovoice_access_key,
        )
        self.interrupt_detector = pvporcupine.create(  # type: ignore[attr-defined]
            keywords=[interrupt_keyword], access_key=settings.picovoice_access_key
        )

        # STT, TTS, and VAD engines
        self.sample_rate = self.wake_detector.sample_rate
        stt_provider = settings.stt_provider

        if stt_provider == "openai":
            if OpenAIWhisperSTT is None:
                raise RuntimeError(
                    "OpenAI STT provider selected but OpenAI client is unavailable"
                )
            if not settings.openai_api_key:
                raise RuntimeError(
                    "OpenAI STT provider selected but OPENAI_API_KEY is not set"
                )
            self.stt = OpenAIWhisperSTT(
                api_key=settings.openai_api_key,
                sample_rate=self.sample_rate,
                endpoint_silence_ms=settings.stt_endpoint_silence_ms,
                min_energy=settings.stt_min_energy,
                model=settings.openai_stt_model,
            )
            print("🧠 Using OpenAI STT provider")
        elif stt_provider == "picovoice":
            self.stt = CheetahSTT(access_key=settings.picovoice_access_key)
        else:
            raise ValueError(f"Unsupported STT provider: {stt_provider}")

        if settings.tts_provider != "picovoice":
            raise ValueError(f"Unsupported TTS provider: {settings.tts_provider}")
        self.tts = OrcaTTS(access_key=settings.picovoice_access_key)

        if settings.vad_provider != "picovoice":
            raise ValueError(f"Unsupported VAD provider: {settings.vad_provider}")
        self.vad = CobraVAD(
            access_key=settings.picovoice_access_key,
            threshold=settings.vad_activation_threshold,
        )

        self.speaker_recogniser: EagleRecogniser | None = None
        self.current_speaker: str | None = None
        self.current_speaker_confidence: float = 0.0
        self.last_identified_speaker: str | None = None
        self.last_identified_confidence: float = 0.0

        if settings.recognition_provider == "picovoice":
            voices_dir = (
                Path(settings.recognition_voices_dir).expanduser()
                if settings.recognition_voices_dir
                else Path(__file__).resolve().parent
                / "audio"
                / "recognition"
                / "eagle"
                / "voices"
            )

            recogniser_instance = EagleRecogniser(
                access_key=settings.picovoice_access_key,
                voices_dir=voices_dir,
                min_score=settings.recognition_min_score,
                smoothing=settings.recognition_smoothing,
                silence_decay=settings.recognition_silence_decay,
            )
            self.speaker_recogniser = recogniser_instance

            if recogniser_instance.sample_rate != self.sample_rate:
                raise RuntimeError(
                    "Eagle recogniser sample rate mismatch with audio input stream"
                )

            print(
                "🆔 Speaker recognition enabled for:",
                ", ".join(recogniser_instance.labels),
            )

        self.conversation_id = self._new_conversation_id()
        self.assistant_base_url = settings.assistant_url.rstrip("/")
        self.conversation_endpoint = f"{self.assistant_base_url}/api/conversation"
        self.assistant_timeout = settings.assistant_timeout
        self.followup_grace = settings.vad_followup_grace
        self.followup_grace_deadline: float | None = None
        self.followup_thread: threading.Thread | None = None

        # Audio buffering for wake pre-roll
        self.frame_length = self.wake_detector.frame_length
        pre_roll_seconds = settings.pre_roll_seconds
        max_frames = max(
            1, int((self.sample_rate * pre_roll_seconds) / self.frame_length)
        )
        self.audio_buffer: Deque[np.ndarray] = deque(maxlen=max_frames)

        # STT session tracking
        self.listening_active = False
        self.partial_transcript: List[str] = []
        self.frame_duration = self.frame_length / self.sample_rate
        self.silence_duration = 0.0

        # Input audio stream shared
        self.stream = sd.InputStream(
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.frame_length,
            dtype="float32",
            callback=self.audio_callback,
        )

        print(
            f"🔊 VoiceAssistant ready: wake={self.wake_keywords}, interrupt='{interrupt_keyword}'"
        )

    def audio_callback(
        self, indata: np.ndarray, frames: int, time_info: Any, status: Any
    ) -> None:
        if status:
            print("Audio status:", status)

        pcm: np.ndarray = np.asarray(indata[:, 0] * 32768, dtype=np.int16)
        self.audio_buffer.append(pcm.copy())
        pcm_list = pcm.tolist()

        if self.state.is_idle():
            if self.wake_detector.process(pcm_list) >= 0:
                self.handle_wake()
                # Process current frame as part of new session
                self._process_stt_frame(pcm)

        elif self.state.mode == "listening":
            self._process_stt_frame(pcm)
        elif self.state.mode == "speaking":
            if self.interrupt_detector.process(pcm_list) >= 0:
                self.handle_interrupt()

    # -------------- Event Handlers ----------------

    def handle_wake(self):
        print("✅ Wake detected")
        self.conversation_id = self._new_conversation_id()
        self.stt.reset()
        self.partial_transcript.clear()
        self.listening_active = True
        self.silence_duration = 0.0
        self.vad.reset()
        self.followup_grace_deadline = None
        self.current_speaker = None
        self.current_speaker_confidence = 0.0
        self.last_identified_speaker = None
        self.last_identified_confidence = 0.0
        if self.speaker_recogniser:
            self.speaker_recogniser.reset()

        # Prime STT with buffered pre-roll audio for natural turn capture
        buffered_frames = list(self.audio_buffer)
        self.audio_buffer.clear()

        self.state.set_state("listening")

        for frame in buffered_frames:
            self._process_stt_frame(frame, from_buffer=True)

    def handle_command(
        self,
        text: str,
        speaker: str | None = None,
        confidence: float | None = None,
    ) -> None:
        if speaker:
            self.last_identified_speaker = speaker
            if confidence is not None:
                self.last_identified_confidence = confidence

        if speaker:
            confidence_note = f" ({confidence:.2f})" if confidence is not None else ""
            print(f"🎤 Heard ({speaker}{confidence_note}):", text)
            self.state.display_text(f"{speaker} said: {text}")
        else:
            print("🎤 Heard:", text)
            self.state.display_text(f"You said: {text}")

        responses, next_action = self.query_assistant(text, speaker=speaker)

        if next_action == "error":
            fallback = "Sorry, I couldn't reach the assistant just now."
            print("⚠️ Assistant unavailable")
            self.state.display_text(fallback)
            self._queue_tts_messages([fallback], next_action="finish")
            return

        self._speak_assistant_messages(responses, next_action)

    def query_assistant(
        self,
        text: str | None = None,
        *,
        speaker: str | None = None,
    ) -> tuple[List[dict[str, str]], str]:
        payload: dict[str, Any] = {
            "text": text,
            "conversation_id": self.conversation_id,
        }

        if speaker:
            payload["speaker"] = speaker

        try:
            response = httpx.post(
                self.conversation_endpoint,
                json=payload,
                timeout=self.assistant_timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"❗️ Assistant request failed: {exc}")
            return [], "error"

        try:
            data = response.json()
        except ValueError:
            print("❗️ Assistant response was not valid JSON")
            return [], "error"

        raw_messages = data.get("messages", [])
        if not isinstance(raw_messages, list):
            return [], "error"

        normalized: List[dict[str, str]] = []
        for raw in cast(List[Any], raw_messages):
            if not isinstance(raw, dict):
                continue
            item = cast(dict[str, Any], raw)
            text_value = str(item.get("text", "")).strip()
            if not text_value:
                continue
            next_value = str(item.get("next", "finish")).lower()
            normalized.append({"text": text_value, "next": next_value})

        next_action = str(data.get("next", "finish")).lower()

        return normalized, next_action

    def _speak_assistant_messages(
        self, responses: List[dict[str, str]], default_next: str
    ) -> tuple[str, bool]:
        next_action = (default_next or "finish").lower()

        if not responses:
            self.on_tts_complete(next_action)
            return next_action, False

        spoken_texts: List[str] = []

        for item in responses:
            text_value = item.get("text", "").strip()
            if not text_value:
                continue
            spoken_texts.append(text_value)
            self.state.display_text(text_value)
            print("🤖 Assistant:", text_value)
            if item.get("next"):
                next_action = str(item["next"]).lower()

        if not spoken_texts:
            self.on_tts_complete(next_action)
            return next_action, False

        self._queue_tts_messages(spoken_texts, next_action=next_action)

        return next_action, True

    def _queue_tts_messages(self, messages: List[str], *, next_action: str) -> None:
        if not messages:
            self.state.set_state("idle")
            return

        action = (next_action or "finish").lower()
        self.state.set_state("speaking")

        last_index = len(messages) - 1

        for index, message in enumerate(messages):
            sanitized = self._sanitize_tts_text(message)
            if not sanitized:
                sanitized = "I'm sorry, I can't read that aloud."
            elif sanitized != message:
                print("ℹ️ Sanitized TTS text to remove unsupported characters")

            if index == last_index:

                def final_callback(act: str = action) -> None:
                    self.on_tts_complete(act)

                try:
                    self.tts.speak(sanitized, on_complete=final_callback)
                except Exception as exc:
                    print(f"⚠️ TTS synthesis failed: {exc}")
                    final_callback()
            else:
                try:
                    self.tts.speak(sanitized)
                except Exception as exc:
                    print(f"⚠️ TTS synthesis failed: {exc}")
                    continue

    def _start_followup_thread(self) -> None:
        if self.followup_thread and self.followup_thread.is_alive():
            return

        def worker() -> None:
            action = "finish"
            spoke = False
            try:
                action, spoke = self._request_followup()
            finally:
                self.followup_thread = None
            if action == "continue" and not spoke:
                self._start_followup_thread()

        self.followup_thread = threading.Thread(target=worker, daemon=True)
        self.followup_thread.start()

    def _request_followup(self) -> tuple[str, bool]:
        speaker_for_followup = (
            self.last_identified_speaker if self.last_identified_speaker else None
        )

        responses, next_action = self.query_assistant(
            None,
            speaker=speaker_for_followup,
        )

        if next_action == "error":
            fallback = "Sorry, I lost connection to the assistant while finishing that request."
            print("⚠️ Assistant follow-up unavailable")
            self.state.display_text(fallback)
            self._queue_tts_messages([fallback], next_action="finish")
            return "finish", True

        final_action, spoke = self._speak_assistant_messages(responses, next_action)
        return final_action, spoke

    def handle_interrupt(self):
        print("🛑 Interrupt: stopping speech")
        self.tts.stop()
        self.listening_active = False
        self.partial_transcript.clear()
        self.silence_duration = 0.0
        self.vad.reset()
        self.audio_buffer.clear()
        self.stt.reset()
        self.state.set_state("idle")
        self.followup_grace_deadline = None
        self.conversation_id = self._new_conversation_id()
        self.current_speaker = None
        self.current_speaker_confidence = 0.0
        self.last_identified_speaker = None
        self.last_identified_confidence = 0.0
        if self.speaker_recogniser:
            self.speaker_recogniser.reset()

    def on_tts_complete(self, next_action: str = "finish") -> None:
        action = (next_action or "finish").lower()

        if action == "wait":
            print("⏳ Awaiting follow-up")
            self.partial_transcript.clear()
            self.listening_active = True
            self.silence_duration = 0.0
            self.audio_buffer.clear()
            self.stt.reset()
            self.vad.reset()
            self.state.set_state("listening")
            self.followup_grace_deadline = time.monotonic() + self.followup_grace
        elif action == "continue":
            self.listening_active = False
            self.state.set_state("thinking")
            self.audio_buffer.clear()
            self.vad.reset()
            self.followup_grace_deadline = None
            self._start_followup_thread()
        else:
            self.listening_active = False
            self.state.set_state("idle")
            self.audio_buffer.clear()
            self.vad.reset()
            self.followup_grace_deadline = None
            self.conversation_id = self._new_conversation_id()

    def _sanitize_tts_text(self, text: str) -> str:
        replacements = {
            "→": " to ",
            "←": " from ",
            "↔": " to ",
            "—": "-",
            "–": "-",
            "…": "...",
            "’": "'",
            "“": '"',
            "”": '"',
            "•": "-",
            ";": "",
            # ":": " -",
            "×": "x",
            "÷": "/",
        }
        table = str.maketrans(replacements)
        sanitized = text.translate(table)
        sanitized = sanitized.replace("<", " ").replace(">", " ")
        sanitized = sanitized.replace("&", "and")
        # Encode/decode to strip any remaining unsupported characters while keeping ASCII.
        sanitized = sanitized.encode("ascii", "ignore").decode("ascii")
        return sanitized.strip()

    def _new_conversation_id(self) -> str:
        return str(uuid.uuid4())

    # -------------- Control ----------------

    def start(self):
        with self.stream:
            while True:
                time.sleep(0.1)

    def stop(self):
        self.wake_detector.delete()
        self.interrupt_detector.delete()
        self.stt.delete()
        self.tts.delete()
        self.vad.delete()
        print("🛑 VoiceAssistant stopped.")

    # -------------- Internal helpers ----------------

    def _process_stt_frame(self, pcm: np.ndarray, *, from_buffer: bool = False) -> None:
        if not self.listening_active:
            return

        voice_probability = self.vad.process(pcm)
        is_voice = voice_probability >= settings.vad_activation_threshold

        now = time.monotonic()

        if self.speaker_recogniser:
            active_label, active_confidence = self.speaker_recogniser.process(
                pcm, voice_detected=is_voice
            )
            if active_label:
                if is_voice and (
                    active_label != self.current_speaker
                    or abs(active_confidence - self.current_speaker_confidence) >= 0.05
                ):
                    print(
                        f"🆔 Speaker likely: {active_label} ({active_confidence:.2f})"
                    )
                self.current_speaker = active_label
                self.current_speaker_confidence = active_confidence
                if active_confidence > self.last_identified_confidence:
                    self.last_identified_speaker = active_label
                    self.last_identified_confidence = active_confidence
            else:
                if not is_voice:
                    self.current_speaker_confidence = active_confidence
                else:
                    self.current_speaker_confidence = active_confidence
                    self.current_speaker = None

        if is_voice:
            self.silence_duration = 0.0
            self.followup_grace_deadline = None
        elif not from_buffer and not self.partial_transcript:
            if (
                self.followup_grace_deadline is not None
                and now < self.followup_grace_deadline
            ):
                # Still within grace window; keep waiting without counting silence yet.
                pass
            else:
                self.followup_grace_deadline = None
                self.silence_duration += self.frame_duration
                if self.silence_duration >= settings.vad_pre_speech_timeout:
                    print("⚠️ No speech detected – timing out listening state.")
                    self.partial_transcript.clear()
                    self.listening_active = False
                    self.audio_buffer.clear()
                    self.silence_duration = 0.0
                    self.vad.reset()
                    self.followup_grace_deadline = None
                    self.current_speaker = None
                    self.current_speaker_confidence = 0.0
                    self.last_identified_speaker = None
                    self.last_identified_confidence = 0.0
                    if self.speaker_recogniser:
                        self.speaker_recogniser.reset()
                    apology = (
                        ""
                        # "I didn't catch anything. Please try again when you're ready."
                    )
                    self.state.display_text(apology)
                    self._queue_tts_messages([apology], next_action="finish")
                    return

        transcript, is_endpoint = self.stt.process(pcm)

        if transcript:
            self.partial_transcript.append(transcript)
            self.state.display_text("".join(self.partial_transcript))

        if is_endpoint:
            final_text = "".join(self.partial_transcript).strip()
            flush_text = self.stt.flush()
            if flush_text:
                if final_text:
                    final_text = f"{final_text} {flush_text}".strip()
                else:
                    final_text = flush_text.strip()

            self.partial_transcript.clear()
            self.listening_active = False
            self.audio_buffer.clear()
            self.silence_duration = 0.0
            self.followup_grace_deadline = None

            if final_text:
                speaker_label: str | None = None
                speaker_confidence: float | None = None

                if self.speaker_recogniser:
                    best_label, best_score = self.speaker_recogniser.best_match()
                    if best_label:
                        speaker_label = best_label
                        speaker_confidence = best_score

                if (
                    not speaker_label
                    and self.last_identified_speaker
                    and self.last_identified_confidence
                    >= (
                        self.speaker_recogniser.min_score
                        if self.speaker_recogniser
                        else settings.recognition_min_score
                    )
                ):
                    speaker_label = self.last_identified_speaker
                    speaker_confidence = self.last_identified_confidence

                if speaker_label and speaker_confidence is not None:
                    self.last_identified_speaker = speaker_label
                    self.last_identified_confidence = speaker_confidence

                self.state.set_state("thinking")
                threading.Thread(
                    target=self.handle_command,
                    args=(final_text, speaker_label, speaker_confidence),
                    daemon=True,
                ).start()
            else:
                self.state.set_state("idle")
            self.vad.reset()


def main():
    assistant = VoiceAssistant()

    def sigint_handler(sig: int, frame: Any) -> None:
        assistant.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sigint_handler)
    assistant.start()


if __name__ == "__main__":
    main()
