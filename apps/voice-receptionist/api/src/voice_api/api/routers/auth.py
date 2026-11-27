"""Authentication: registration and token issuance."""

from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from voice_api.api.deps import Session
from voice_api.config import get_settings
from voice_api.models import AgentConfig, Business, Tenant, User
from voice_api.schemas import RegisterRequest, TokenResponse, UserOut
from voice_api.security import CurrentUser, create_access_token, hash_password, verify_password
from voice_api.services.bookings import default_hours

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = _SLUG.sub("-", value.lower()).strip("-")
    return f"{slug or 'tenant'}-{uuid.uuid4().hex[:6]}"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: Session) -> TokenResponse:
    tenant = Tenant(name=payload.tenant_name, slug=slugify(payload.tenant_name))
    session.add(tenant)
    await session.flush()
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user = User(
        tenant_id=tenant.id,
        email=payload.email.lower(),
        full_name=payload.full_name,
        password_hash=password_hash,
        role="admin",
    )
    session.add(user)
    business = Business(
        tenant_id=tenant.id,
        name=payload.business_name,
        timezone=payload.timezone,
        hours=default_hours(),
        services=[
            {"name": "Consultation", "duration_minutes": 30, "price_cents": 0},
        ],
        greeting=(
            f"Thanks for calling {payload.business_name}. I'm the automated receptionist. "
            "How can I help you today?"
        ),
    )
    session.add(business)
    await session.flush()
    session.add(
        AgentConfig(
            tenant_id=tenant.id,
            business_id=business.id,
            name="Default receptionist",
            prompt=(
                "You are the friendly receptionist for the business. Qualify the caller, "
                "check availability, book appointments, and text a booking link. "
                "Never claim to be human."
            ),
        )
    )
    token = create_access_token(str(user.id), str(tenant.id), user.role)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_ttl_minutes * 60,
        tenant_id=tenant.id,
        role=user.role,
    )


@router.post("/token", response_model=TokenResponse)
async def token(
    session: Session,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == form.username.lower()))
    user = result.scalar_one_or_none()
    if not user or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(str(user.id), str(user.tenant_id), user.role),
        expires_in=settings.jwt_ttl_minutes * 60,
        tenant_id=user.tenant_id,
        role=user.role,
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
