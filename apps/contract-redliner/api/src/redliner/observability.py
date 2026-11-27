"""Structured JSON logging + Langfuse tracing.

Langfuse is optional: when keys are absent the decorators are no-ops. This is
deliberate — local development and CI must run without external services.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from typing import Any, TypeVar

from redliner.config import get_settings

settings = get_settings()
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")

F = TypeVar("F", bound=Callable[..., Any])


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


# ------------------------------------------------------------------ Langfuse
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
    except Exception:  # pragma: no cover - optional dependency/network
        _langfuse = None
    return _langfuse


def langfuse_enabled() -> bool:
    return _get_langfuse() is not None


@contextmanager
def trace_span(name: str, **metadata: Any) -> Iterator[dict[str, Any]]:
    """Context manager that records timing and optional Langfuse metadata."""
    started = time.perf_counter()
    span: dict[str, Any] = {"name": name, "metadata": metadata, "started": started}
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
        if obs is not None:
            with suppress(Exception):
                obs.update(status_message=str(exc), level="ERROR")
        raise
    finally:
        span["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        if obs is not None:
            with suppress(Exception):
                obs.end()
        get_logger("trace").info("span", extra={"context": span})


def trace_generation(name: str, model: str, **metadata: Any) -> Any:
    """Decorator factory for LLM generations (best-effort Langfuse)."""
    client = _get_langfuse()

    def decorator(fn: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if client is None:
                return fn(*args, **kwargs)
            try:
                with client.generation(name=name, model=model, metadata=metadata or None) as gen:
                    result = fn(*args, **kwargs)
                    if isinstance(result, dict):
                        gen.update(output=result.get("output"), usage=result.get("usage"))
                    return result
            except Exception:  # pragma: no cover - tracing must never break prod
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
