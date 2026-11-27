"""Application settings.

All secrets are read from the environment. The settings object is cached so
pydantic-settings only parses the environment once per process.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["dev", "staging", "prod"] = "dev"
    app_name: str = "ClauseGuard API"
    api_prefix: str = "/v1"
    public_api_prefix: str = "/api/clause/v1"

    # Database
    database_url: str = "postgresql+asyncpg://redliner:redliner@localhost:5432/redliner"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False
    db_pool_recycle: int = 1800
    db_statement_timeout_ms: int = 30_000

    # Redis / queue
    redis_url: str = "redis://localhost:6379/0"

    # Abuse control
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 120
    rate_limit_burst: int = 20

    # Auth
    jwt_secret: str = Field(default="dev-only-change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 60 * 12
    api_key_prefix: str = "cg_live_"
    auth_lockout_threshold: int = 5
    auth_lockout_minutes: int = 15
    email_verification_required: bool = False
    mfa_required: bool = False
    email_from: str = "no-reply@clauseguard.local"
    smtp_url: str | None = None

    # Uploads
    max_upload_mb: int = 100
    max_pages: int = 300

    # Storage
    storage_backend: Literal["local", "s3"] = "local"
    local_storage_dir: str = ".data/storage"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # LLM providers
    llm_provider: Literal["openai", "anthropic", "stub"] = "openai"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    llm_temperature: float = 0.0
    llm_timeout_s: float = 60.0
    llm_max_repair_attempts: int = 2

    # Embeddings
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    embedding_batch_size: int = 64

    # PDF extraction
    llamacloud_api_key: str | None = None
    unstructured_api_key: str | None = None
    pdf_provider: Literal["local", "llamaparse", "unstructured"] = "local"

    # Search
    rrf_k: int = 60
    hybrid_limit: int = 20

    # Cache
    cache_enabled: bool = True
    cache_ttl_seconds: int = 60
    embedding_cache_ttl_seconds: int = 86_400

    # Quality / cost budgets
    citation_validation_enabled: bool = True
    max_tokens_per_document: int = 200_000
    target_review_seconds: int = 180
    cost_alert_usd: float = 0.40

    # Observability
    log_level: str = "INFO"
    log_json: bool = True
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    metrics_enabled: bool = True

    # Billing / quotas
    billing_enabled: bool = False
    plan_limits: dict[str, int] = {
        "trial": 10,
        "pro": 500,
        "enterprise": 100_000,
    }

    # CORS
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

    @field_validator("cors_origins")
    @classmethod
    def _split_origins(cls, value: str) -> str:
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        return False

    @property
    def embeddings_configured(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
