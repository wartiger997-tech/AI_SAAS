"""API and internal Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Severity = Literal["critical", "high", "medium", "low", "info"]
ReviewStatus = Literal["queued", "extracting", "reviewing", "completed", "failed"]
FindingStatus = Literal["open", "accepted", "rejected", "dismissed"]
ReviewerRole = Literal["customer", "vendor", "buyer", "seller", "licensor", "licensee"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth
class RegisterRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    full_name: str = Field(default="", max_length=200)


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


# ---------------------------------------------------------------- documents
class DocumentOut(ORMModel):
    id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    page_count: int
    status: str
    error: str | None = None
    created_at: datetime


class ClauseOut(ORMModel):
    id: uuid.UUID
    page: int
    heading: str
    text: str
    clause_type: str
    confidence: float


class PageOut(BaseModel):
    page: int
    text: str
    width: float
    height: float
    tables: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------- playbooks
class RuleOut(BaseModel):
    id: str
    title: str
    category: str
    severity: Severity
    description: str = ""
    patterns: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    market_standard: str = ""
    guidance: str = ""
    suggested_text: str = ""
    redline_strategy: Literal["replace", "insert_after", "delete", "flag"] = "flag"
    applies_to: list[str] = Field(default_factory=list)
    weight: float = 1.0


class PlaybookCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = ""
    rules: list[RuleOut] = Field(min_length=1)

    @field_validator("rules")
    @classmethod
    def _unique_ids(cls, rules: list[RuleOut]) -> list[RuleOut]:
        ids = [r.id for r in rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule ids must be unique")
        return rules


class PlaybookOut(ORMModel):
    id: uuid.UUID
    name: str
    version: int
    description: str
    is_active: bool
    created_at: datetime
    rule_count: int = 0


# ---------------------------------------------------------------- reviews
class ReviewCreate(BaseModel):
    playbook_id: uuid.UUID
    reviewer_role: ReviewerRole = "customer"


class FindingOut(ORMModel):
    id: uuid.UUID
    rule_id: str
    title: str
    severity: Severity
    status: FindingStatus
    quote: str
    page: int
    suggested_text: str
    rationale: str
    market_standard: str
    confidence: float
    clause_id: uuid.UUID
    reviewer_note: str = ""


class FindingPatch(BaseModel):
    status: FindingStatus | None = None
    reviewer_note: str | None = Field(default=None, max_length=4000)


class ReviewOut(ORMModel):
    id: uuid.UUID
    document_id: uuid.UUID
    playbook_id: uuid.UUID
    reviewer_role: str
    status: ReviewStatus
    progress: int
    model: str
    error: str | None = None
    created_at: datetime
    finding_count: int = 0


class ReviewDetail(ReviewOut):
    document: DocumentOut
    findings: list[FindingOut] = Field(default_factory=list)


class ExportRequest(BaseModel):
    format: Literal["docx", "pdf", "md", "json"]
    include_dismissed: bool = False


class ExportResponse(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    url: str


# ---------------------------------------------------------------- search
class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=10, ge=1, le=50)
    source: str | None = None


class SearchHit(BaseModel):
    id: uuid.UUID
    title: str
    source: str
    score: float
    snippet: str


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
    took_ms: int


# ---------------------------------------------------------------- health
class HealthResponse(BaseModel):
    status: str
    version: str
    checks: dict[str, str] = Field(default_factory=dict)
