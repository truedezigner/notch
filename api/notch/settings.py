from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    TZ: str = "America/Los_Angeles"

    APP_BASE_URL: str = "http://192.168.29.228:8083"
    APP_PORT: int = 8080

    DB_PATH: str = "/data/app.db"

    # Auth
    SESSION_SECRET: str
    SESSION_DAYS: int = 30

    # Tuesday integration
    SERVICE_TOKEN: str
    SERVICE_USER_HANDLE: str | None = None

    # NTFY
    NTFY_BASE_URL: str = "http://192.168.29.228:8082"
    NTFY_TOPIC_PREFIX: str = "tuesday-"

    # Scheduler
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_POLL_SECONDS: float = 1.0


settings = Settings()
