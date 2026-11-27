"""Pydantic schemas for the Relay control plane."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Outcome = Literal[
    "booked",
    "transferred",
    "message_taken",
    "callback_requested",
    "not_interested",
    "wrong_number",
    "voicemail",
    "abandoned",
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ auth
class RegisterRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=200)
    business_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    full_name: str = Field(default="", max_length=200)
    timezone: str = Field(default="America/New_York", max_length=64)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int
    tenant_id: uuid.UUID
    role: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    tenant_id: uuid.UUID


# ------------------------------------------------------------------ business
class ServiceItem(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    duration_minutes: int = Field(default=30, ge=5, le=480)
    price_cents: int = Field(default=0, ge=0)


class BusinessCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    timezone: str = Field(default="America/New_York", max_length=64)
    address: str = Field(default="", max_length=1000)
    phone: str = Field(default="", max_length=32)
    hours: dict[str, list[list[str]]] = Field(default_factory=dict)
    services: list[ServiceItem] = Field(default_factory=list)
    greeting: str = Field(default="", max_length=2000)
    after_hours_message: str = Field(default="", max_length=2000)
    consent_required: bool = True
    recording_enabled: bool = True


class BusinessUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    timezone: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=1000)
    phone: str | None = Field(default=None, max_length=32)
    hours: dict[str, list[list[str]]] | None = None
    services: list[ServiceItem] | None = None
    greeting: str | None = Field(default=None, max_length=2000)
    after_hours_message: str | None = Field(default=None, max_length=2000)
    consent_required: bool | None = None
    recording_enabled: bool | None = None
    is_active: bool | None = None


class BusinessOut(ORMModel):
    id: uuid.UUID
    name: str
    timezone: str
    address: str
    phone: str
    hours: dict[str, Any]
    services: list[dict[str, Any]]
    greeting: str
    after_hours_message: str
    consent_required: bool
    recording_enabled: bool
    is_active: bool


# ------------------------------------------------------------------ agent
class AgentCreate(BaseModel):
    business_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    voice_id: str = Field(default="21m00Tcm4TlvDq8ikWAM", max_length=120)
    stt_model: str = Field(default="nova-3", max_length=80)
    tts_model: str = Field(default="eleven_turbo_v2_5", max_length=80)
    llm_model: str = Field(default="baidu/ernie-5.5-flash-preview:free", max_length=120)
    prompt: str = Field(default="", max_length=12000)


class AgentOut(ORMModel):
    id: uuid.UUID
    business_id: uuid.UUID
    name: str
    voice_id: str
    stt_model: str
    tts_model: str
    llm_model: str
    prompt: str
    is_active: bool


# ------------------------------------------------------------------ numbers
class PhoneCreate(BaseModel):
    business_id: uuid.UUID
    e164: str = Field(min_length=7, max_length=32)
    label: str = Field(default="", max_length=120)
    direction: Literal["inbound", "outbound", "both"] = "inbound"

    @field_validator("e164")
    @classmethod
    def _validate_e164(cls, value: str) -> str:
        if not value.startswith("+"):
            raise ValueError("e164 must start with +")
        if not value[1:].isdigit():
            raise ValueError("e164 must contain only digits after +")
        return value


class PhoneOut(ORMModel):
    id: uuid.UUID
    business_id: uuid.UUID
    e164: str
    label: str
    direction: str
    is_active: bool


# ------------------------------------------------------------------ calls
class CallOutbound(BaseModel):
    to_number: str = Field(min_length=7, max_length=32)
    contact_name: str = Field(default="", max_length=200)
    contact_phone: str = Field(default="", max_length=32)
    business_id: uuid.UUID
    campaign: str = Field(default="", max_length=120)
    agent_config_id: uuid.UUID | None = None


class CallOut(ORMModel):
    id: uuid.UUID
    business_id: uuid.UUID
    direction: str
    from_number: str
    to_number: str
    contact_name: str
    contact_phone: str
    status: str
    outcome: str | None
    summary: str
    duration_s: int
    consent_recorded: bool
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime


class TurnOut(ORMModel):
    seq: int
    role: str
    content: str
    ts_ms: int
    redacted: bool


class CallDetail(CallOut):
    turns: list[TurnOut] = Field(default_factory=list)
    recording_url: str = ""


# ------------------------------------------------------------------ availability
class AvailabilityQuery(BaseModel):
    business_id: uuid.UUID
    date: date
    days: int = Field(default=1, ge=1, le=14)
    slot_minutes: int = Field(default=30, ge=5, le=240)
    service: str | None = Field(default=None, max_length=160)


class SlotOut(BaseModel):
    starts_at: datetime
    ends_at: datetime
    service: str


class AvailabilityResponse(BaseModel):
    business_id: uuid.UUID
    timezone: str
    slots: list[SlotOut]


# ------------------------------------------------------------------ bookings
class BookingCreate(BaseModel):
    business_id: uuid.UUID
    starts_at: datetime
    service: str = Field(min_length=1, max_length=160)
    contact_name: str = Field(min_length=1, max_length=200)
    contact_phone: str = Field(min_length=7, max_length=32)
    call_id: uuid.UUID | None = None
    notes: str = Field(default="", max_length=2000)


class BookingOut(ORMModel):
    id: uuid.UUID
    business_id: uuid.UUID
    call_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    service: str
    status: str
    contact_name: str
    contact_phone: str
    notes: str


class BookingCreated(BookingOut):
    booking_url: str


# ------------------------------------------------------------------ knowledge
class KnowledgeCreate(BaseModel):
    business_id: uuid.UUID
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=20000)
    source: str = Field(default="manual", max_length=300)


class KnowledgeOut(ORMModel):
    id: uuid.UUID
    business_id: uuid.UUID
    title: str
    content: str
    source: str


# ------------------------------------------------------------------ misc
class HealthResponse(BaseModel):
    status: str
    version: str
    checks: dict[str, str] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    detail: str
