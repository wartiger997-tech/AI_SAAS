"""Tests for environment configuration."""

from __future__ import annotations

import pytest

from receptionist_agent.config import AgentSettings


def test_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "internal")
    monkeypatch.setenv("RELAY_API_URL", "http://relay-api:8001")
    monkeypatch.setenv("RELAY_API_PREFIX", "/api/relay/v1")
    settings = AgentSettings.from_env()
    settings.require()
    assert settings.control_plane_url == "http://relay-api:8001"
    assert settings.control_plane_prefix == "/api/relay/v1"


def test_require_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
        "INTERNAL_API_TOKEN",
        "RELAY_API_URL",
        "CONTROL_PLANE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = AgentSettings.from_env()
    with pytest.raises(RuntimeError):
        settings.require()
