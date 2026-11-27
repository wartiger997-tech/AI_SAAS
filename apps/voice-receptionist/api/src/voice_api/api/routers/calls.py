"""Call control: outbound initiation, listing, and detail."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from voice_api.api.deps import Session, UserDep
from voice_api.models import Business, Call, DncEntry, TranscriptTurn
from voice_api.schemas import CallDetail, CallOut, CallOutbound, TurnOut
from voice_api.services.bookings import normalize_phone
from voice_api.services.jobs import enqueue_outbound

router = APIRouter(prefix="/calls", tags=["calls"])


@router.post("/outbound", response_model=CallOut, status_code=status.HTTP_202_ACCEPTED)
async def outbound(session: Session, user: UserDep, payload: CallOutbound) -> CallOut:
    business = await session.get(Business, payload.business_id)
    if not business or business.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="business not found")
    phone = normalize_phone(payload.to_number)
    if not phone:
        raise HTTPException(status_code=422, detail="invalid destination number")
    dnc = await session.execute(
        select(DncEntry).where(DncEntry.tenant_id == user.tenant_id, DncEntry.phone == phone)
    )
    if dnc.scalar_one_or_none():
        raise HTTPException(status_code=422, detail="number is on the do-not-call list")
    call = Call(
        tenant_id=user.tenant_id,
        business_id=business.id,
        direction="outbound",
        from_number=business.phone,
        to_number=phone,
        contact_name=payload.contact_name,
        contact_phone=phone,
        status="queued",
        meta={"campaign": payload.campaign, "agent_config_id": str(payload.agent_config_id or "")},
    )
    session.add(call)
    await session.commit()
    await session.refresh(call)
    try:
        await enqueue_outbound(call.id)
    except Exception as exc:  # noqa: BLE001
        call.status = "failed"
        call.meta = {**(call.meta or {}), "error": f"enqueue failed: {exc}"}
        await session.commit()
        raise HTTPException(status_code=503, detail="call queue unavailable") from exc
    return CallOut.model_validate(call)


@router.get("", response_model=list[CallOut])
async def list_calls(
    session: Session,
    user: UserDep,
    business_id: uuid.UUID | None = None,
    call_status: str | None = Query(default=None, alias="status"),
    direction: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CallOut]:
    query = select(Call).where(Call.tenant_id == user.tenant_id)
    if business_id:
        query = query.where(Call.business_id == business_id)
    if call_status:
        query = query.where(Call.status == call_status)
    if direction:
        query = query.where(Call.direction == direction)
    result = await session.execute(query.order_by(Call.created_at.desc()).limit(limit))
    return [CallOut.model_validate(call) for call in result.scalars()]


@router.get("/{call_id}", response_model=CallDetail)
async def get_call(session: Session, user: UserDep, call_id: uuid.UUID) -> CallDetail:
    call = await session.get(Call, call_id)
    if not call or call.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="call not found")
    result = await session.execute(
        select(TranscriptTurn).where(TranscriptTurn.call_id == call.id).order_by(TranscriptTurn.seq)
    )
    base = CallOut.model_validate(call)
    detail = CallDetail(**base.model_dump())
    detail.turns = [TurnOut.model_validate(turn) for turn in result.scalars()]
    return detail


@router.post("/{call_id}/end", response_model=CallOut)
async def end_call(session: Session, user: UserDep, call_id: uuid.UUID) -> CallOut:
    call = await session.get(Call, call_id)
    if not call or call.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="call not found")
    if call.status not in {"completed", "failed"}:
        call.status = "completed"
        await session.commit()
        await session.refresh(call)
    return CallOut.model_validate(call)
