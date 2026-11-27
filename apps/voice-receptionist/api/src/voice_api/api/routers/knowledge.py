"""Knowledge base documents used by the agent's lookup tool."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from voice_api.api.deps import Session, UserDep
from voice_api.models import Business, KnowledgeDoc
from voice_api.schemas import KnowledgeCreate, KnowledgeOut

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("", response_model=list[KnowledgeOut])
async def list_knowledge(
    session: Session, user: UserDep, business_id: uuid.UUID | None = None
) -> list[KnowledgeOut]:
    query = select(KnowledgeDoc).where(KnowledgeDoc.tenant_id == user.tenant_id)
    if business_id:
        query = query.where(KnowledgeDoc.business_id == business_id)
    result = await session.execute(query.order_by(KnowledgeDoc.created_at.desc()))
    return [KnowledgeOut.model_validate(doc) for doc in result.scalars()]


@router.post("", response_model=KnowledgeOut, status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    session: Session, user: UserDep, payload: KnowledgeCreate
) -> KnowledgeOut:
    business = await session.get(Business, payload.business_id)
    if not business or business.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="business not found")
    doc = KnowledgeDoc(
        tenant_id=user.tenant_id,
        business_id=payload.business_id,
        title=payload.title,
        content=payload.content,
        source=payload.source,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return KnowledgeOut.model_validate(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge(session: Session, user: UserDep, doc_id: uuid.UUID) -> None:
    doc = await session.get(KnowledgeDoc, doc_id)
    if not doc or doc.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="document not found")
    await session.delete(doc)
    await session.commit()
