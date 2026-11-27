"""Document upload/validation service."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from redliner.config import get_settings
from redliner.models import Document
from redliner.storage import checksum, put_bytes, storage_key

settings = get_settings()
_PDF_MAGIC = b"%PDF-"


class UnsupportedDocument(ValueError):
    pass


class DocumentTooLarge(ValueError):
    pass


async def create_document(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    filename: str,
    data: bytes,
    content_type: str = "application/pdf",
) -> Document:
    if not data:
        raise UnsupportedDocument("empty upload")
    if len(data) > settings.max_upload_bytes:
        raise DocumentTooLarge(f"upload exceeds {settings.max_upload_mb} MB")
    if content_type not in {"application/pdf", "application/octet-stream"}:
        raise UnsupportedDocument("only PDF uploads are supported in v1")
    if not data.lstrip()[:5].startswith(_PDF_MAGIC):
        raise UnsupportedDocument("file is not a valid PDF")

    key = storage_key(filename, str(tenant_id))
    put_bytes(key, data, content_type="application/pdf")
    document = Document(
        tenant_id=tenant_id,
        filename=filename[:400],
        mime_type="application/pdf",
        size_bytes=len(data),
        storage_key=key,
        checksum=checksum(data),
        status="uploaded",
    )
    session.add(document)
    await session.flush()
    return document
