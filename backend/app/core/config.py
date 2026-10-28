"""Environment-based application settings."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, HttpUrl, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Product Demand Analyzer API"
    environment: str = "development"
    database_url: PostgresDsn
    log_level: str = "INFO"
    auth_enabled: bool = False
    jwt_signing_secret: SecretStr = SecretStr("")
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "ai-product-demand-analyzer"
    jwt_audience: str = "demand-analyzer-browser"
    auth_access_token_minutes: int = Field(default=30, ge=1, le=120)
    auth_allowed_origins: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]
    auth_login_requests_per_minute: int = Field(default=10, ge=1, le=30)
    operator_token: SecretStr = SecretStr("")
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    public_demo_enabled: bool = False
    demo_database_url: PostgresDsn | None = None
    demo_ai_enabled: bool = False
    demo_reads_per_minute: int = Field(default=120, ge=1, le=1000)
    demo_ai_requests_per_minute: int = Field(default=3, ge=1, le=10)
    demo_ai_daily_cap: int = Field(default=10, ge=1, le=100)
    max_request_bytes: int = Field(default=26 * 1024 * 1024, gt=0)
    ai_usage_file: str = ""
    ai_requests_per_minute: int = Field(default=10, ge=1, le=100)
    ai_daily_request_cap: int = Field(default=100, ge=1, le=10000)
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    recommendation_increase_threshold_percent: Decimal = Field(default=Decimal("10"), gt=0)
    recommendation_reduce_threshold_percent: Decimal = Field(default=Decimal("-10"), lt=0)
    ai_enabled: bool = False
    ai_provider: Literal["ollama", "openai"] = "ollama"
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

    @field_validator("ai_base_url", "demo_database_url", mode="before")
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
        if self.environment not in {"development", "test", "production"}:
            raise ValueError("Unknown ENVIRONMENT")
        if self.environment == "production":
            if not self.auth_enabled:
                raise ValueError("Production requires AUTH_ENABLED=true")
            if not self.auth_allowed_origins or any(
                not origin.startswith("https://") for origin in self.auth_allowed_origins
            ):
                raise ValueError("Production requires explicit HTTPS AUTH_ALLOWED_ORIGINS")
            if not self.trusted_hosts or "*" in self.trusted_hosts:
                raise ValueError("Production requires explicit TRUSTED_HOSTS")
            if self.ai_enabled and self.ai_provider != "openai":
                raise ValueError("Production AI requires hosted inference")
        if self.ai_enabled and self.ai_provider == "openai":
            if (
                not self.ai_api_key.get_secret_value()
                or self.ai_api_key.get_secret_value() == "ollama"
            ):
                raise ValueError("Hosted inference requires AI_API_KEY")
            if self.ai_base_url.scheme != "https":
                raise ValueError("Hosted inference requires HTTPS")
        if self.auth_enabled:
            if len(self.jwt_signing_secret.get_secret_value()) < 64:
                raise ValueError("JWT_SIGNING_SECRET requires at least 64 random characters")
            if not self.jwt_issuer or not self.jwt_audience:
                raise ValueError("JWT issuer and audience must be nonempty")
            for origin in self.auth_allowed_origins:
                parsed = urlsplit(origin)
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.path
                    or parsed.query
                    or parsed.fragment
                    or "*" in origin
                ):
                    raise ValueError("Auth origins must be exact scheme/host/port origins")
        if self.public_demo_enabled:
            if self.environment != "production" or self.demo_database_url is None:
                raise ValueError("Public demo requires production and a separate demo reader URL")
            if (
                len(self.demo_database_url.hosts()) != 1
                or self.demo_database_url.hosts()[0]["username"] != "demand_demo_reader"
            ):
                raise ValueError("Demo URL must use the read-only demand_demo_reader role")
            if not self.demo_database_url.path.rstrip("/").endswith("_demo"):
                raise ValueError("Public data must use a dedicated *_demo database")
        if self.demo_ai_enabled and not (self.public_demo_enabled and self.ai_enabled):
            raise ValueError("Public AI requires public demo and explicitly enabled hosted AI")
        if self.demo_ai_enabled and not self.ai_usage_file:
            raise ValueError("Public AI requires persistent usage accounting")
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached validated settings."""
    return Settings()
