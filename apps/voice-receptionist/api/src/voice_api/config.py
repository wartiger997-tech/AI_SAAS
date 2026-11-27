"""Relay Receptionist control-plane settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["dev", "staging", "prod"] = "dev"
    app_name: str = "Relay Receptionist API"
    api_prefix: str = "/v1"
    public_api_prefix: str = "/api/relay/v1"

    database_url: str = "postgresql+asyncpg://relay:relay@localhost:5432/relay"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False
    db_pool_recycle: int = 1800
    db_statement_timeout_ms: int = 30_000

    redis_url: str = "redis://localhost:6379/1"

    # Abuse control
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 120
    rate_limit_burst: int = 20

    jwt_secret: str = Field(default="dev-only-change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 60 * 12
    internal_api_token: str = Field(default="dev-internal-token", min_length=8)
    auth_lockout_threshold: int = 5
    auth_lockout_minutes: int = 15
    email_verification_required: bool = False
    mfa_required: bool = False
    email_from: str = "no-reply@relay.local"
    smtp_url: str | None = None

    # Telephony
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None
    twilio_api_base: str = "https://api.twilio.com/2010-04-01"

    # LiveKit
    livekit_url: str = "wss://your-project.livekit.cloud"
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None
    livekit_sip_uri: str = "sip:relay@sip.livekit.cloud;transport=tcp"
    agent_name: str = "relay-receptionist"

    # Providers — OpenRouter free models are the default.
    deepgram_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    llm_provider: Literal["openrouter", "openai", "stub"] = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "baidu/ernie-5.5-flash-preview:free"
    openrouter_fallback_models: str = (
        "google/gemma-4-31b-it:free,nvidia/nemotron-3.5-lightning:free"
    )
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    llm_timeout_s: float = 20.0

    # Booking / messaging
    booking_link_base_url: str = "http://localhost:8001"
    booking_lead_minutes: int = 60
    default_slot_minutes: int = 30
    default_service_minutes: int = 30
    booking_link_ttl_minutes: int = 60 * 24

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    local_storage_dir: str = ".data/storage"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # Cache
    cache_enabled: bool = True
    cache_ttl_seconds: int = 30

    # Billing / quotas
    billing_enabled: bool = False
    plan_limits: dict[str, int] = {
        "trial": 100,
        "pro": 5_000,
        "enterprise": 1_000_000,
    }

    # Retention / safety
    transcript_retention_days: int = 90
    recording_retention_days: int = 30
    max_call_seconds: int = 900
    quiet_hours_start: int = 21
    quiet_hours_end: int = 8

    # Observability
    log_level: str = "INFO"
    log_json: bool = True
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    metrics_enabled: bool = True

    cors_origins: str = "http://localhost:3000"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Accept Render/Heroku ``postgres://`` URLs and asyncpg URLs."""
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "openrouter":
            return bool(self.openrouter_api_key)
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        return False

    @property
    def openrouter_model_list(self) -> list[str]:
        models = [self.openrouter_model]
        models.extend(
            model.strip()
            for model in self.openrouter_fallback_models.split(",")
            if model.strip() and model.strip() not in models
        )
        return models

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)

    @property
    def telephony_configured(self) -> bool:
        return self.twilio_configured and bool(self.livekit_api_key and self.livekit_api_secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
