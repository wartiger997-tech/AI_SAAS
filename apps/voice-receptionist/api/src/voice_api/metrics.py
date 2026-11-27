"""Prometheus metrics.

The client is optional at import time so tests and local development do not
require the dependency. Every helper is a no-op when ``prometheus_client`` is
unavailable.
"""

from __future__ import annotations

try:  # pragma: no cover - exercised implicitly
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
except Exception:  # pragma: no cover
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    Counter = Histogram = None  # type: ignore[assignment]
    generate_latest = None  # type: ignore[assignment]

REQUEST_COUNT = (
    Counter(
        "http_requests_total",
        "Total HTTP requests.",
        ["method", "route", "status"],
    )
    if Counter
    else None
)
REQUEST_LATENCY = (
    Histogram(
        "http_request_duration_seconds",
        "HTTP request latency.",
        ["method", "route"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )
    if Histogram
    else None
)
LLM_LATENCY = (
    Histogram(
        "llm_request_duration_seconds",
        "LLM call latency.",
        ["provider", "model"],
        buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 40),
    )
    if Histogram
    else None
)
LLM_TOKENS = (
    Counter(
        "llm_tokens_total",
        "LLM tokens consumed.",
        ["model", "kind"],
    )
    if Counter
    else None
)
REVIEW_DURATION = (
    Histogram(
        "review_duration_seconds",
        "End-to-end review duration.",
        buckets=(5, 15, 30, 60, 120, 180, 300, 600),
    )
    if Histogram
    else None
)
FINDINGS_CREATED = (
    Counter("findings_created_total", "Findings created.", ["severity"]) if Counter else None
)
CACHE_EVENTS = (
    Counter("cache_events_total", "Cache hits and misses.", ["cache", "result"])
    if Counter
    else None
)
BOOKING_CONFLICTS = (
    Counter("booking_conflicts_total", "Booking conflicts rejected.") if Counter else None
)
RATE_LIMITED = (
    Counter("rate_limited_total", "Requests rejected by the rate limiter.") if Counter else None
)
CITATION_REJECTED = (
    Counter("citation_rejected_total", "Findings rejected by the citation gate.")
    if Counter
    else None
)
BUDGET_EXCEEDED = (
    Counter("budget_exceeded_total", "Requests that exceeded a budget.", ["kind"])
    if Counter
    else None
)


def observe_request(method: str, route: str, status: int, duration_s: float) -> None:
    if REQUEST_COUNT:
        REQUEST_COUNT.labels(method, route, str(status)).inc()
    if REQUEST_LATENCY:
        REQUEST_LATENCY.labels(method, route).observe(duration_s)


def observe_llm(
    provider: str, model: str, duration_s: float, tokens: dict[str, int] | None = None
) -> None:
    if LLM_LATENCY:
        LLM_LATENCY.labels(provider, model).observe(duration_s)
    if LLM_TOKENS and tokens:
        for kind, value in tokens.items():
            if value:
                LLM_TOKENS.labels(model, kind).inc(value)


def observe_review(duration_s: float, severities: dict[str, int] | None = None) -> None:
    if REVIEW_DURATION:
        REVIEW_DURATION.observe(duration_s)
    if FINDINGS_CREATED and severities:
        for severity, count in severities.items():
            if count:
                FINDINGS_CREATED.labels(severity).inc(count)


def observe_cache(cache: str, hit: bool) -> None:
    if CACHE_EVENTS:
        CACHE_EVENTS.labels(cache, "hit" if hit else "miss").inc()


def observe_booking_conflict() -> None:
    if BOOKING_CONFLICTS:
        BOOKING_CONFLICTS.inc()


def observe_rate_limited() -> None:
    if RATE_LIMITED:
        RATE_LIMITED.inc()


def observe_citation_rejected() -> None:
    if CITATION_REJECTED:
        CITATION_REJECTED.inc()


def observe_budget(kind: str) -> None:
    if BUDGET_EXCEEDED:
        BUDGET_EXCEEDED.labels(kind).inc()


def render_metrics() -> tuple[bytes, str]:
    if generate_latest is None:
        return b"# metrics unavailable\n", "text/plain; charset=utf-8"
    return generate_latest(), CONTENT_TYPE_LATEST


def metrics_enabled() -> bool:
    return generate_latest is not None


__all__ = [
    "metrics_enabled",
    "observe_booking_conflict",
    "observe_budget",
    "observe_cache",
    "observe_citation_rejected",
    "observe_llm",
    "observe_rate_limited",
    "observe_request",
    "observe_review",
    "render_metrics",
]
