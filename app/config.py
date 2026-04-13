from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SoundSentinel"
    environment: str = "development"
    debug: bool = True
    app_version: str = "0.1.0"

    postgres_user: str = "soundsentinel"
    postgres_password: str = "soundsentinel"
    postgres_db: str = "soundsentinel"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    database_url_override: Optional[str] = None
    max_audio_upload_bytes: int = 2_000_000
    spike_peak_threshold: float = 0.8
    sustained_noise_threshold: float = 0.2
    sustained_noise_window_seconds: int = 1
    repeated_peak_threshold: float = 0.55
    repeated_peak_window_seconds: int = 2
    repeated_peak_min_count: int = 3
    alert_cooldown_seconds: int = 60
    sensor_offline_threshold_seconds: int = 120
    telegram_api_base_url: str = "https://api.telegram.org"
    notification_request_timeout_seconds: int = 10
    database_init_max_attempts: int = 30
    database_init_retry_delay_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="SOUNDSENTINEL_",
    )

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override

        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
