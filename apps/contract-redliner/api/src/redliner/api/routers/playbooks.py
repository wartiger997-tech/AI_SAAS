"""Playbook CRUD and activation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from redliner.api.deps import Session
from redliner.models import Playbook
from redliner.schemas import PlaybookCreate, PlaybookOut
from redliner.security import CurrentUser

router = APIRouter(prefix="/playbooks", tags=["playbooks"])


def _to_out(playbook: Playbook, rule_count: int) -> PlaybookOut:
    data = PlaybookOut.model_validate(playbook)
    data.rule_count = rule_count
    return data


@router.get("", response_model=list[PlaybookOut])
async def list_playbooks(session: Session, user: CurrentUser) -> list[PlaybookOut]:
    result = await session.execute(
        select(Playbook).where(Playbook.tenant_id == user.tenant_id).order_by(Playbook.name)
    )
    return [_to_out(p, len(p.rules or [])) for p in result.scalars()]


@router.post("", response_model=PlaybookOut, status_code=status.HTTP_201_CREATED)
async def create_playbook(
    session: Session, user: CurrentUser, payload: PlaybookCreate
) -> PlaybookOut:
    latest = await session.execute(
        select(func.max(Playbook.version)).where(
            Playbook.tenant_id == user.tenant_id, Playbook.name == payload.name
        )
    )
    version = int(latest.scalar() or 0) + 1
    playbook = Playbook(
        tenant_id=user.tenant_id,
        name=payload.name,
        version=version,
        description=payload.description,
        rules=[rule.model_dump() for rule in payload.rules],
    )
    session.add(playbook)
    await session.commit()
    await session.refresh(playbook)
    return _to_out(playbook, len(playbook.rules))


@router.get("/{playbook_id}", response_model=PlaybookOut)
async def get_playbook(session: Session, user: CurrentUser, playbook_id: uuid.UUID) -> PlaybookOut:
    playbook = await session.get(Playbook, playbook_id)
    if not playbook or playbook.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="playbook not found")
    return _to_out(playbook, len(playbook.rules))


@router.post("/{playbook_id}/activate", response_model=PlaybookOut)
async def activate_playbook(
    session: Session, user: CurrentUser, playbook_id: uuid.UUID
) -> PlaybookOut:
    playbook = await session.get(Playbook, playbook_id)
    if not playbook or playbook.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="playbook not found")
    await session.execute(
        Playbook.__table__.update()
        .where(Playbook.tenant_id == user.tenant_id, Playbook.name == playbook.name)
        .values(is_active=False)
    )
    playbook.is_active = True
    await session.commit()
    await session.refresh(playbook)
    return _to_out(playbook, len(playbook.rules))
