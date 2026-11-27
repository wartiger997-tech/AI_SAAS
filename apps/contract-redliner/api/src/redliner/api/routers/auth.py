"""Authentication: registration, token issuance, current user."""

from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from redliner.api.deps import Session
from redliner.config import get_settings
from redliner.models import Tenant, User
from redliner.schemas import RegisterRequest, TokenResponse, UserOut
from redliner.security import CurrentUser, create_access_token, hash_password, verify_password
from redliner.services.playbook import seed_default_playbooks

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = _SLUG.sub("-", value.lower()).strip("-")
    return f"{slug or 'tenant'}-{uuid.uuid4().hex[:6]}"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: Session) -> TokenResponse:
    existing = await session.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="email already registered")
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
    await session.flush()
    await seed_default_playbooks(session, tenant)
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
    access = create_access_token(str(user.id), str(user.tenant_id), user.role)
    return TokenResponse(
        access_token=access,
        expires_in=settings.jwt_ttl_minutes * 60,
        tenant_id=user.tenant_id,
        role=user.role,
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
