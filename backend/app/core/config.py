"""Environment-based application settings."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Product Demand Analyzer API"
    environment: str = "development"
    database_url: PostgresDsn
    log_level: str = "INFO"
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    recommendation_increase_threshold_percent: Decimal = Field(default=Decimal("10"), gt=0)
    recommendation_reduce_threshold_percent: Decimal = Field(default=Decimal("-10"), lt=0)
    ai_enabled: bool = False
    ai_provider: Literal["ollama"] = "ollama"
    ai_base_url: HttpUrl | None = None
    ai_model: str = Field(default="", max_length=500)
    ai_api_key: SecretStr = SecretStr("ollama")
    ai_temperature: float = Field(default=0.2, ge=0, le=2)
    ai_ollama_transport: Literal["native", "openai"] = "native"
    ai_num_ctx: int = Field(default=8192, ge=2048, le=32768)
    ai_timeout_seconds: float = Field(default=120, ge=1, le=300)
    ai_max_context_records: int = Field(default=100, ge=1, le=100)
    ai_max_retrieval_series: int = Field(default=1000, ge=100, le=5000)
    ai_max_history_messages: int = Field(default=10, ge=2, le=10)
    ai_max_output_tokens: int = Field(default=512, ge=32, le=1024)
    ai_context_char_limit: int = Field(default=8000, ge=2000, le=24000)
    ai_conversation_ttl_seconds: int = Field(default=1800, ge=60, le=86400)
    ai_max_conversations: int = Field(default=128, ge=1, le=1000)
    ai_max_concurrent_requests: int = Field(default=1, ge=1, le=8)

    @field_validator("ai_base_url", mode="before")
    @classmethod
    def empty_ai_url(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_ai_configuration(self):
        if self.ai_enabled and (self.ai_base_url is None or not self.ai_model.strip()):
            raise ValueError("Enabled AI requires AI_BASE_URL and AI_MODEL")
        if self.ai_base_url and (self.ai_base_url.username or self.ai_base_url.password):
            raise ValueError("Use AI_API_KEY instead of credentials in AI_BASE_URL")
        if self.ai_base_url and not self.ai_base_url.path.rstrip("/").endswith("/v1"):
            raise ValueError("AI_BASE_URL must end in /v1")
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached validated settings."""
    return Settings()
