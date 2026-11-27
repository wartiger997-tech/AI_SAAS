"""Shared FastAPI dependencies."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from redliner.db import get_session
from redliner.models import User
from redliner.security import CurrentUser

Session = Annotated[AsyncSession, Depends(get_session)]


def require_tenant(user: CurrentUser) -> uuid.UUID:
    return user.tenant_id


def require_role(*roles: str):
    def _checker(user: CurrentUser) -> User:
        if user.role not in roles and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role {user.role} not permitted",
            )
        return user

    return _checker
