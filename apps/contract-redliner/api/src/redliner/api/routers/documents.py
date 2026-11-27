"""Document upload and retrieval."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from redliner.api.deps import Session
from redliner.models import Document
from redliner.schemas import DocumentOut, PageOut
from redliner.security import CurrentUser
from redliner.services.documents import (
    DocumentTooLarge,
    UnsupportedDocument,
    create_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    session: Session,
    user: CurrentUser,
    file: Annotated[UploadFile, File(...)],
) -> DocumentOut:
    data = await file.read()
    try:
        document = await create_document(
            session,
            tenant_id=user.tenant_id,
            filename=file.filename or "contract.pdf",
            data=data,
            content_type=file.content_type or "application/pdf",
        )
    except DocumentTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except UnsupportedDocument as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    await session.commit()
    await session.refresh(document)
    return DocumentOut.model_validate(document)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    session: Session,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[DocumentOut]:
    result = await session.execute(
        select(Document)
        .where(Document.tenant_id == user.tenant_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [DocumentOut.model_validate(doc) for doc in result.scalars()]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(session: Session, user: CurrentUser, document_id: uuid.UUID) -> DocumentOut:
    document = await session.get(Document, document_id)
    if not document or document.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="document not found")
    return DocumentOut.model_validate(document)


@router.get("/{document_id}/pages", response_model=list[PageOut])
async def get_pages(session: Session, user: CurrentUser, document_id: uuid.UUID) -> list[PageOut]:
    document = await session.get(Document, document_id)
    if not document or document.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="document not found")
    if not document.extracted:
        raise HTTPException(status_code=409, detail="document has not been extracted yet")
    return [PageOut.model_validate(page) for page in document.extracted.get("pages", [])]
