from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import TENCENT_OCR_DEFAULTS


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: float
    key: str


def rate_limit_key(provider: str, region: str | None, action: str) -> str:
    return f"ocr:rate_limit:{provider}:{region or 'global'}:{action}"


def effective_qps(provider_config: Any) -> int:
    configured_qps = max(int(getattr(provider_config, "qps_limit", 1) or 1), 1)
    if getattr(provider_config, "provider", None) == TENCENT_OCR_DEFAULTS.provider:
        return min(configured_qps, TENCENT_OCR_DEFAULTS.qps_limit)
    return configured_qps


class RedisTokenBucketRateLimiter:
    def __init__(self, redis_client) -> None:
        self.redis_client = redis_client

    def acquire(
        self,
        provider: str,
        region: str | None,
        action: str,
        qps_limit: int,
        *,
        now_ms: int | None = None,
    ) -> RateLimitDecision:
        qps_limit = max(int(qps_limit or 1), 1)
        now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        key = rate_limit_key(provider, region, action)
        state = self.redis_client.hgetall(key)
        capacity = float(qps_limit)
        tokens = _state_float(state, "tokens", capacity)
        updated_at_ms = _state_float(state, "updated_at_ms", float(now_ms))

        elapsed_ms = max(now_ms - updated_at_ms, 0)
        tokens = min(capacity, tokens + (elapsed_ms / 1000.0) * qps_limit)
        allowed = tokens >= 1.0
        if allowed:
            tokens -= 1.0
            retry_after_seconds = 0.0
        else:
            retry_after_seconds = (1.0 - tokens) / qps_limit

        self.redis_client.hset(
            key,
            mapping={
                "tokens": f"{tokens:.6f}",
                "updated_at_ms": str(now_ms),
            },
        )
        self.redis_client.expire(key, max(2, math.ceil((capacity / qps_limit) * 2)))
        return RateLimitDecision(
            allowed=allowed,
            retry_after_seconds=round(retry_after_seconds, 3),
            key=key,
        )


def _state_float(state: dict[Any, Any], name: str, default: float) -> float:
    value = state.get(name, state.get(name.encode("utf-8")))
    if value is None:
        return default
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
