"""Structured JSON logging and optional Langfuse tracing."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from typing import Any

from voice_api.config import get_settings

settings = get_settings()
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "trace_id": trace_id_var.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "context", None)
        if isinstance(extra, dict):
            payload.update(extra)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:16]
    request_id_var.set(rid)
    trace_id_var.set(rid)
    return rid


_langfuse: Any | None = None
_langfuse_ready = False


def _get_langfuse() -> Any | None:
    global _langfuse, _langfuse_ready
    if _langfuse_ready:
        return _langfuse
    _langfuse_ready = True
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:  # pragma: no cover
        _langfuse = None
    return _langfuse


@contextmanager
def trace_span(name: str, **metadata: Any) -> Iterator[dict[str, Any]]:
    started = time.perf_counter()
    span: dict[str, Any] = {"name": name, "metadata": metadata}
    client = _get_langfuse()
    obs = None
    if client is not None:
        try:
            obs = client.span(name=name, metadata=metadata or None)
        except Exception:  # pragma: no cover
            obs = None
    try:
        yield span
    except Exception as exc:
        span["error"] = str(exc)
        raise
    finally:
        span["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        if obs is not None:
            with suppress(Exception):
                obs.end()
        get_logger("trace").info("span", extra={"context": span})


_sentry_ready = False


def init_error_tracking() -> None:
    """Initialize Sentry when a DSN is configured. Never raises."""
    global _sentry_ready
    if _sentry_ready:
        return
    _sentry_ready = True
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.env,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=0.0,
            send_default_pii=False,
        )
    except Exception:  # pragma: no cover - telemetry must never break the app
        get_logger(__name__).debug("sentry initialization failed", exc_info=True)
