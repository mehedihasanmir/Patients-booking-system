from __future__ import annotations

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_agent_name: str = "bytevoice"
    api_base_url: str = "http://localhost:8000"
    service_token: str = "dev-service-token-change-me"
    tts_provider: str = "auto"
    stt_provider: str = "auto"
    openai_stt_model: str = "gpt-4o-mini-transcribe"
    openai_stt_language: str = "bn"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "coral"
    google_tts_voice: str = "bn-IN-Wavenet-A"
    log_level: str = "INFO"

    @property
    def google_ready(self) -> bool:
        import os

        return bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))


def get_settings() -> Settings:
    return Settings()
