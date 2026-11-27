"""ORM models.

Design notes:
- Every tenant-scoped table carries ``tenant_id`` and a composite FK/index so
  row-level security and tenant filters can be added without a migration.
- AI payloads are stored as JSON so model upgrades do not require DDL changes.
- Citations are first-class columns, not nested blobs, so they can be indexed
  and validated in SQL.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from redliner.config import get_settings
from redliner.db import Base

_UUID = UUID(as_uuid=True)
_JSON = JSONB().with_variant(JSON(), "sqlite")


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="trial", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list[User]] = relationship(back_populates="tenant")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="reviewer", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="users")


class ApiKey(TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Document(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_tenant_status", "tenant_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(400), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), default="application/pdf")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(600), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", nullable=False)
    error: Mapped[str | None] = mapped_column(Text())
    extracted: Mapped[dict[str, Any] | None] = mapped_column(_JSON)

    clauses: Mapped[list[Clause]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[Review]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Clause(Base):
    __tablename__ = "clauses"
    __table_args__ = (
        UniqueConstraint("document_id", "block_id", name="uq_clauses_doc_block"),
        Index("ix_clauses_doc_page", "document_id", "page"),
    )

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    block_id: Mapped[str] = mapped_column(String(80), nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    clause_type: Mapped[str] = mapped_column(String(64), default="general")
    char_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bbox: Mapped[dict[str, float] | None] = mapped_column(_JSON)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    document: Mapped[Document] = relationship(back_populates="clauses")
    findings: Mapped[list[Finding]] = relationship(
        back_populates="clause", cascade="all, delete-orphan"
    )


class Playbook(TimestampMixin, Base):
    __tablename__ = "playbooks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", "version", name="uq_playbook_name_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(_JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    playbook_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("playbooks.id", ondelete="RESTRICT"), nullable=False
    )
    reviewer_role: Mapped[str] = mapped_column(String(32), default="customer")
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    usage: Mapped[dict[str, Any] | None] = mapped_column(_JSON)
    error: Mapped[str | None] = mapped_column(Text())

    document: Mapped[Document] = relationship(back_populates="reviews")
    findings: Mapped[list[Finding]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("review_id", "clause_id", "rule_id", name="uq_finding_unique"),
        Index("ix_findings_review_severity", "review_id", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    review_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )
    clause_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("clauses.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="open", nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    suggested_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    market_standard: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(_JSON)
    reviewer_note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    review: Mapped[Review] = relationship(back_populates="findings")
    clause: Mapped[Clause] = relationship(back_populates="findings")
    redlines: Mapped[list[Redline]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class Redline(Base):
    __tablename__ = "redlines"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    finding_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    old_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    new_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    anchor: Mapped[str] = mapped_column(Text, default="", nullable=False)
    accepted: Mapped[bool | None] = mapped_column(Boolean)

    finding: Mapped[Finding] = relationship(back_populates="redlines")


class PrecedentChunk(TimestampMixin, Base):
    __tablename__ = "precedent_chunks"
    __table_args__ = (
        Index(
            "ix_precedent_tenant_source",
            "tenant_id",
            "source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(get_settings().embedding_dim))
    meta: Mapped[dict[str, Any] | None] = mapped_column(_JSON)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_tenant_created", "tenant_id", "created_at"),)

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
    "ApiKey",
    "Clause",
    "Document",
    "Finding",
    "Playbook",
    "PrecedentChunk",
    "Redline",
    "Review",
    "Tenant",
    "User",
    "AuditEvent",
]
