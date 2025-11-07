"""Production-grade token bucket rate limiter with observability hooks."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Final

import redis
from prometheus_client import Counter
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Prometheus metric to track denied requests
rate_limited_total: Final[Counter] = Counter(
    "rate_limited_requests_total",
    "Total rate-limited requests",
    ["user_id"],
)

# Initialize OpenTelemetry tracing once for the process
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
span_processor = BatchSpanProcessor(ConsoleSpanExporter())
trace.get_tracer_provider().add_span_processor(span_processor)


def _build_redis_client() -> redis.Redis:
    """Build a Redis client using environment overrides when present."""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return redis.Redis.from_url(redis_url, decode_responses=True)
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        decode_responses=True,
    )


r = _build_redis_client()

_LUA_PATH = Path(__file__).resolve().parent / "lua" / "token_bucket.lua"
with _LUA_PATH.open("r", encoding="utf-8") as lua_file:
    token_bucket_script = r.register_script(lua_file.read())


def is_allowed(user_id: str, max_tokens: int = 100, refill_per_minute: int = 100) -> bool:
    """
    Token bucket rate limiter with full observability.

    :param user_id: identity used to partition the bucket.
    :param max_tokens: maximum burst capacity.
    :param refill_per_minute: steady-state refill rate in tokens/minute.
    """
    key = f"tb:{user_id}"
    now_ms = int(time.time() * 1000)
    max_scaled = max_tokens * 1000  # operate on micro-tokens to avoid float math
    refill_rate_scaled = (refill_per_minute * 1000) / 60000.0  # micro-tokens per ms

    with tracer.start_as_current_span("rate_limit_check") as span:
        span.set_attribute("user.id", user_id)
        span.set_attribute("rate_limit.max_tokens", max_tokens)
        span.set_attribute("rate_limit.refill_per_min", refill_per_minute)

        allowed = bool(
            token_bucket_script(
                keys=[key],
                args=[max_scaled, refill_rate_scaled, now_ms],
            )
        )

        span.set_attribute("rate_limit.allowed", allowed)
        if not allowed:
            span.add_event("Rate limit exceeded")
            rate_limited_total.labels(user_id=user_id).inc()

        return allowed
