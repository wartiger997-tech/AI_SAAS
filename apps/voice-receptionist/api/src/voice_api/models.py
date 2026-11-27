"""ORM models for the Relay control plane.

Invariants encoded in the schema:
- every tenant-owned row carries ``tenant_id``;
- appointments have a partial unique index on ``(business_id, starts_at)`` for
  non-cancelled rows, so a double booking is impossible even under concurrency;
- webhook events are idempotent on ``(provider, event_id)``;
- transcripts are separate rows so redaction/retention can be applied per turn.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voice_api.db import Base

_UUID = UUID(as_uuid=True)
_JSON = JSONB().with_variant(JSON(), "sqlite")


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="trial", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_relay_users_tenant_email"),)

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="admin", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Business(TimestampMixin, Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York", nullable=False)
    address: Mapped[str] = mapped_column(Text, default="", nullable=False)
    phone: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    hours: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False)
    services: Mapped[list[dict[str, Any]]] = mapped_column(_JSON, nullable=False)
    greeting: Mapped[str] = mapped_column(Text, default="", nullable=False)
    after_hours_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    consent_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recording_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    agents: Mapped[list[AgentConfig]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )
    numbers: Mapped[list[PhoneNumber]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )


class AgentConfig(TimestampMixin, Base):
    __tablename__ = "agent_configs"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    voice_id: Mapped[str] = mapped_column(
        String(120), default="21m00Tcm4TlvDq8ikWAM", nullable=False
    )
    stt_model: Mapped[str] = mapped_column(String(80), default="nova-3", nullable=False)
    tts_model: Mapped[str] = mapped_column(String(80), default="eleven_turbo_v2_5", nullable=False)
    llm_model: Mapped[str] = mapped_column(
        String(120), default="baidu/ernie-5.5-flash-preview:free", nullable=False
    )
    prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped[Business] = relationship(back_populates="agents")


class PhoneNumber(TimestampMixin, Base):
    __tablename__ = "phone_numbers"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    e164: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    twilio_sid: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    direction: Mapped[str] = mapped_column(String(16), default="inbound", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business: Mapped[Business] = relationship(back_populates="numbers")


class Call(TimestampMixin, Base):
    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_calls_tenant_started", "tenant_id", "started_at"),
        Index("ix_calls_business_status", "business_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(16), default="inbound", nullable=False)
    provider_call_sid: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    from_number: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    to_number: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    contact_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recording_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    consent_recorded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict[str, Any] | None] = mapped_column(_JSON)

    turns: Mapped[list[TranscriptTurn]] = relationship(
        back_populates="call",
        cascade="all, delete-orphan",
        order_by="TranscriptTurn.seq",
    )


class TranscriptTurn(Base):
    __tablename__ = "transcript_turns"
    __table_args__ = (
        UniqueConstraint("call_id", "seq", name="uq_turn_call_seq"),
        Index("ix_turns_call_seq", "call_id", "seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    call_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    ts_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    redacted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    call: Mapped[Call] = relationship(back_populates="turns")


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index(
            "uq_appointment_business_start",
            "business_id",
            "starts_at",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
            sqlite_where=text("status <> 'cancelled'"),
        ),
        Index("ix_appointments_business_start", "business_id", "starts_at"),
        CheckConstraint("ends_at > starts_at", name="ck_appointment_window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    call_id: Mapped[uuid.UUID | None] = mapped_column(
        _UUID, ForeignKey("calls.id", ondelete="SET NULL")
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    service: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="confirmed", nullable=False)
    contact_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class BookingLink(TimestampMixin, Base):
    __tablename__ = "booking_links"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sms_sid: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeDoc(TimestampMixin, Base):
    __tablename__ = "knowledge_docs"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(300), default="manual", nullable=False)


class DncEntry(TimestampMixin, Base):
    __tablename__ = "dnc_entries"
    __table_args__ = (UniqueConstraint("tenant_id", "phone", name="uq_dnc_tenant_phone"),)

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), default="", nullable=False)


class WebhookEvent(TimestampMixin, Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_webhook_provider_event"),)

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(32), default="twilio", nullable=False)
    event_id: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_relay_audit_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="SET NULL")
    )
    actor: Mapped[str] = mapped_column(String(200), default="system", nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(_JSON)
    ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = [
    "AgentConfig",
    "Appointment",
    "AuditEvent",
    "BookingLink",
    "Business",
    "Call",
    "DncEntry",
    "KnowledgeDoc",
    "PhoneNumber",
    "Tenant",
    "TranscriptTurn",
    "User",
    "WebhookEvent",
]
