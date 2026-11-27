"""FastAPI dependencies."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from voice_api.db import get_session
from voice_api.models import User
from voice_api.security import CurrentUser, InternalToken

Session = Annotated[AsyncSession, Depends(get_session)]
UserDep = CurrentUser
Internal = InternalToken


def require_tenant(user: CurrentUser) -> uuid.UUID:
    return user.tenant_id


def require_role(*roles: str):
    def _checker(user: CurrentUser) -> User:
        if user.role not in roles and user.role != "admin":
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role {user.role} not permitted",
            )
        return user

    return _checker
