"""Tests for password hashing and JWT."""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi import HTTPException

from voice_api.config import get_settings
from voice_api.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_roundtrip() -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("scrypt$")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong", encoded)


def test_password_policy() -> None:
    with pytest.raises(ValueError):
        hash_password("short")


def test_jwt_roundtrip() -> None:
    token = create_access_token("user-1", "tenant-1", "admin")
    claims = decode_access_token(token)
    assert claims["sub"] == "user-1"
    assert claims["tid"] == "tenant-1"
    assert claims["role"] == "admin"


def test_jwt_expired() -> None:
    settings = get_settings()
    now = int(time.time())
    token = jwt.encode(
        {"sub": "u", "tid": "t", "exp": now - 10},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(HTTPException):
        decode_access_token(token)


def test_invalid_token() -> None:
    with pytest.raises(HTTPException):
        decode_access_token("not-a-token")
