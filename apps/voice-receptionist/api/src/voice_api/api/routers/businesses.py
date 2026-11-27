"""Business configuration."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from voice_api.api.deps import Session, UserDep
from voice_api.models import Business
from voice_api.schemas import BusinessCreate, BusinessOut, BusinessUpdate

router = APIRouter(prefix="/businesses", tags=["businesses"])


async def _load(session: Session, user: UserDep, business_id: uuid.UUID) -> Business:
    business = await session.get(Business, business_id)
    if not business or business.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="business not found")
    return business


@router.get("", response_model=list[BusinessOut])
async def list_businesses(session: Session, user: UserDep) -> list[BusinessOut]:
    result = await session.execute(
        select(Business).where(Business.tenant_id == user.tenant_id).order_by(Business.created_at)
    )
    return [BusinessOut.model_validate(item) for item in result.scalars()]


@router.post("", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
async def create_business(session: Session, user: UserDep, payload: BusinessCreate) -> BusinessOut:
    business = Business(
        tenant_id=user.tenant_id,
        name=payload.name,
        timezone=payload.timezone,
        address=payload.address,
        phone=payload.phone,
        hours=payload.hours or {},
        services=[service.model_dump() for service in payload.services],
        greeting=payload.greeting,
        after_hours_message=payload.after_hours_message,
        consent_required=payload.consent_required,
        recording_enabled=payload.recording_enabled,
    )
    session.add(business)
    await session.commit()
    await session.refresh(business)
    return BusinessOut.model_validate(business)


@router.get("/{business_id}", response_model=BusinessOut)
async def get_business(session: Session, user: UserDep, business_id: uuid.UUID) -> BusinessOut:
    return BusinessOut.model_validate(await _load(session, user, business_id))


@router.patch("/{business_id}", response_model=BusinessOut)
async def update_business(
    session: Session, user: UserDep, business_id: uuid.UUID, payload: BusinessUpdate
) -> BusinessOut:
    business = await _load(session, user, business_id)
    data = payload.model_dump(exclude_unset=True)
    if "services" in data and data["services"] is not None:
        data["services"] = [
            service.model_dump() if hasattr(service, "model_dump") else service
            for service in data["services"]
        ]
    for field, value in data.items():
        setattr(business, field, value)
    await session.commit()
    await session.refresh(business)
    return BusinessOut.model_validate(business)
