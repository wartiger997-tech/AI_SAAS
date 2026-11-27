"""Smoke tests for the ASGI app (no database required)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from voice_api.main import app


def test_root_and_health() -> None:
    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert root.json()["docs"] == "/docs"
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert client.get("/api/relay/v1/healthz").status_code == 200
        assert client.get("/metrics").status_code == 200


def test_openapi_lists_routes() -> None:
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        paths = schema["paths"]
        assert "/v1/auth/register" in paths
        assert "/v1/calls/outbound" in paths
        assert "/v1/availability" in paths
        assert "/v1/webhooks/twilio/inbound" in paths


def test_register_schema_requires_business_name() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/auth/register",
            json={"tenant_name": "Acme", "email": "a@b.co", "password": "longenough1"},
        )
        assert response.status_code == 422
