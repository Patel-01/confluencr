from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Transaction Webhook Service", validation_alias="APP_NAME")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )
    database_url: str = Field(
        default="sqlite:///./transactions.db", validation_alias="DATABASE_URL"
    )
    processing_delay_seconds: float = Field(
        default=30.0, validation_alias="PROCESSING_DELAY_SECONDS", ge=0
    )
    worker_max_workers: int = Field(default=4, validation_alias="WORKER_MAX_WORKERS", ge=1)
    worker_lease_seconds: int = Field(default=120, validation_alias="WORKER_LEASE_SECONDS", ge=1)
    worker_max_attempts: int = Field(default=3, validation_alias="WORKER_MAX_ATTEMPTS", ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()

