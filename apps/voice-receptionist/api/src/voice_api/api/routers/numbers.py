"""Phone number provisioning."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from voice_api.api.deps import Session, UserDep
from voice_api.models import Business, PhoneNumber
from voice_api.schemas import PhoneCreate, PhoneOut

router = APIRouter(prefix="/numbers", tags=["numbers"])


@router.get("", response_model=list[PhoneOut])
async def list_numbers(session: Session, user: UserDep) -> list[PhoneOut]:
    result = await session.execute(
        select(PhoneNumber)
        .where(PhoneNumber.tenant_id == user.tenant_id)
        .order_by(PhoneNumber.created_at)
    )
    return [PhoneOut.model_validate(number) for number in result.scalars()]


@router.post("", response_model=PhoneOut, status_code=status.HTTP_201_CREATED)
async def create_number(session: Session, user: UserDep, payload: PhoneCreate) -> PhoneOut:
    business = await session.get(Business, payload.business_id)
    if not business or business.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="business not found")
    existing = await session.execute(select(PhoneNumber).where(PhoneNumber.e164 == payload.e164))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="number already provisioned")
    number = PhoneNumber(
        tenant_id=user.tenant_id,
        business_id=payload.business_id,
        e164=payload.e164,
        label=payload.label,
        direction=payload.direction,
    )
    session.add(number)
    await session.commit()
    await session.refresh(number)
    return PhoneOut.model_validate(number)


@router.delete("/{number_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_number(session: Session, user: UserDep, number_id: uuid.UUID) -> None:
    number = await session.get(PhoneNumber, number_id)
    if not number or number.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="number not found")
    await session.delete(number)
    await session.commit()
