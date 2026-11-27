"""Initial schema: pgvector + all ClauseGuard tables.

We use metadata.create_all inside the migration for the initial revision because
the schema is large and declarative; subsequent revisions are hand-written.

Revision ID: 0001_initial
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from redliner.db import Base
from redliner import models  # noqa: F401

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)
    # HNSW index for the embedding column (created after data load in prod).
    bind.execute(
        "CREATE INDEX IF NOT EXISTS ix_precedent_embedding_hnsw "
        "ON precedent_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute("DROP INDEX IF EXISTS ix_precedent_embedding_hnsw")
    Base.metadata.drop_all(bind=bind)