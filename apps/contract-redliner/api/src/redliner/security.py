"""Password hashing, JWT, and API-key authentication.

Password hashing uses scrypt from the standard library: no native build step,
memory-hard, and adequate for a B2B SaaS. API keys are stored as SHA-256
digests with a short public prefix for support and rotation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from redliner.config import get_settings
from redliner.db import get_session
from redliner.models import ApiKey, User

settings = get_settings()

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("password must be at least 10 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN
    )
    return (
        f"scrypt${_SCRYPT_N}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n_raw, salt_b64, digest_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode(),
            salt=salt,
            n=int(n_raw),
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, tenant_id: str, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "tid": tenant_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, str]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if not payload.get("sub") or not payload.get("tid"):
        raise HTTPException(status_code=401, detail="malformed token")
    return {
        "sub": str(payload["sub"]),
        "tid": str(payload["tid"]),
        "role": str(payload.get("role")),
    }


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    raw = settings.api_key_prefix + secrets.token_urlsafe(32)
    prefix = raw[: len(settings.api_key_prefix) + 6]
    return raw, prefix, _hash_key(raw)


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    if x_api_key:
        digest = _hash_key(x_api_key)
        result = await session.execute(
            select(ApiKey).where(ApiKey.key_hash == digest, ApiKey.revoked_at.is_(None))
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise HTTPException(status_code=401, detail="invalid API key")
        # Resolve a user in the tenant; API keys act as the tenant's service identity.
        result = await session.execute(
            select(User).where(User.tenant_id == api_key.tenant_id, User.is_active.is_(True))
        )
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=401, detail="no active user for API key")
        api_key.last_used_at = datetime.now(UTC)
        return user

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = decode_access_token(authorization.split(" ", 1)[1].strip())
    user = await session.get(User, uuid.UUID(claims["sub"]))
    if not user or not user.is_active or str(user.tenant_id) != claims["tid"]:
        raise HTTPException(status_code=401, detail="user not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
