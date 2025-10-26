from typing import Literal, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Wakeword settings
    wake_provider: Literal["picovoice"] = "picovoice"
    wakewords: list[str] = ["jarvis"]
    wakeword_sensitivities: list[float] = [0.6]

    # Picovoice API key (used for all Picovoice services: Porcupine, Cheetah, Orca)
    picovoice_access_key: str = ""

    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    pre_roll_seconds: float = 1.5
    audio_input_device: int | str | None = None
    audio_output_device: int | str | None = None

    # Voice activity detection (Cobra)
    vad_provider: Literal["picovoice"] = "picovoice"
    vad_activation_threshold: float = 0.7
    vad_pre_speech_timeout: float = 4
    vad_followup_grace: float = 1.0

    # STT settings
    stt_provider: Literal["picovoice", "openai"] = "picovoice"
    openai_api_key: Optional[str] = None
    openai_stt_model: str = "gpt-4o-mini-transcribe"
    stt_endpoint_silence_ms: int = 900
    stt_min_energy: float = 60.0

    # TTS settings
    tts_provider: Literal["picovoice"] = "picovoice"

    # Speaker recognition
    recognition_provider: Literal["none", "picovoice"] = "picovoice"
    recognition_min_score: float = 0.5
    recognition_voices_dir: Optional[str] = None
    recognition_smoothing: float = 0.4
    recognition_silence_decay: float = 0.95

    # Backend communication
    backend_url: str = "http://localhost:8000"
    websocket_url: str = "ws://localhost:8000/ws"
    assistant_url: str = "http://localhost:8001"
    assistant_timeout: float = 60.0

    # Interrupt detection
    interrupt_enabled: bool = True
    interrupt_words: list[str] = ["stop", "cancel", "nevermind"]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()  # type: ignore
