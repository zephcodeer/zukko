from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    tts_voice: str = "uz-UZ-MadinaNeural"
    database_path: Path = Path("data/zukko.db")
    cache_dir: Path = Path("data/audio_cache")
    api_timeout_seconds: float = Field(default=12.0, ge=2, le=60)
    log_level: str = "INFO"


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

