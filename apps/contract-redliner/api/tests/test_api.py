"""Smoke tests for the ASGI app (no database required)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from redliner.main import app


def test_root_and_health() -> None:
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/clause/v1/healthz").status_code == 200
        assert client.get("/metrics").status_code == 200


def test_openapi_lists_routes() -> None:
    with TestClient(app) as client:
        paths = client.get("/openapi.json").json()["paths"]
        assert "/v1/auth/register" in paths
        assert "/v1/documents" in paths
