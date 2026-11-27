"""Relay Receptionist control-plane FastAPI application."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from voice_api.api.routers import (
    agents,
    auth,
    availability,
    bookings,
    businesses,
    calls,
    health,
    internal,
    knowledge,
    numbers,
    webhooks,
)
from voice_api.config import get_settings
from voice_api.db import dispose_engine
from voice_api.metrics import observe_request
from voice_api.observability import (
    configure_logging,
    get_logger,
    init_error_tracking,
    new_request_id,
    request_id_var,
)

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_error_tracking()
    logger.info("app.starting", extra={"context": {"env": settings.env}})
    yield
    await dispose_engine()
    logger.info("app.stopped")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request.failed", extra={"context": {"path": request.url.path}})
            raise
        duration = time.perf_counter() - started
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-ms"] = str(int(duration * 1000))
        route = request.scope.get("route")
        observe_request(
            request.method,
            getattr(route, "path", request.url.path),
            response.status_code,
            duration,
        )
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Response-Time-ms"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.exception_handler(OSError)
    async def dependency_unavailable(request: Request, exc: OSError):
        logger.error(
            "dependency.unavailable",
            extra={"context": {"path": request.url.path, "error": str(exc)}},
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "A required dependency is unavailable. Check DATABASE_URL, REDIS_URL, "
                    "and object-storage configuration."
                )
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.errors(), "body": exc.body})

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, Any]:
        return {
            "name": settings.app_name,
            "docs": "/docs",
            "health": "/healthz",
            "ready": "/readyz",
            "telephony_configured": settings.telephony_configured,
        }

    prefixes = [settings.api_prefix]
    if settings.public_api_prefix and settings.public_api_prefix not in prefixes:
        prefixes.append(settings.public_api_prefix)

    app.include_router(health.router)
    for prefix in prefixes:
        app.include_router(health.router, prefix=prefix, include_in_schema=False)

    for prefix in prefixes:
        primary = prefix == settings.api_prefix
        app.include_router(auth.router, prefix=prefix, include_in_schema=primary)
        app.include_router(businesses.router, prefix=prefix, include_in_schema=primary)
        app.include_router(agents.router, prefix=prefix, include_in_schema=primary)
        app.include_router(numbers.router, prefix=prefix, include_in_schema=primary)
        app.include_router(calls.router, prefix=prefix, include_in_schema=primary)
        app.include_router(availability.router, prefix=prefix, include_in_schema=primary)
        app.include_router(bookings.router, prefix=prefix, include_in_schema=primary)
        app.include_router(knowledge.router, prefix=prefix, include_in_schema=primary)
        app.include_router(internal.router, prefix=prefix, include_in_schema=primary)
        app.include_router(webhooks.router, prefix=prefix, include_in_schema=primary)
    return app


app = create_app()
