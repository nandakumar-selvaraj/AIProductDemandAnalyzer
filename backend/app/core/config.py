"""Environment-based application settings."""

from functools import lru_cache

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Product Demand Analyzer API"
    environment: str = "development"
    database_url: PostgresDsn
    log_level: str = "INFO"
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached validated settings."""
    return Settings()
