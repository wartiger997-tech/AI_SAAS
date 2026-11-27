"""Relay Receptionist control-plane settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["dev", "staging", "prod"] = "dev"
    app_name: str = "Relay Receptionist API"
    api_prefix: str = "/v1"

    database_url: str = "postgresql+asyncpg://relay:relay@localhost:5432/relay"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    redis_url: str = "redis://localhost:6379/1"

    jwt_secret: str = Field(default="dev-only-change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 60 * 12
    internal_api_token: str = Field(default="dev-internal-token", min_length=8)

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

    # Providers
    deepgram_api_key: str | None = None
    elevenlabs_api_key: str | None = None
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

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)

    @property
    def telephony_configured(self) -> bool:
        return self.twilio_configured and bool(self.livekit_api_key and self.livekit_api_secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
