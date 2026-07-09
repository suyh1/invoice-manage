from types import SimpleNamespace

from app.domain.ocr.rate_limiter import RedisTokenBucketRateLimiter, effective_qps, rate_limit_key


class FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.expirations: dict[str, int] = {}

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def hset(self, key: str, mapping: dict[str, str]) -> None:
        self.hashes.setdefault(key, {}).update(mapping)

    def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds


def test_rate_limiter_allows_burst_and_refills_tokens() -> None:
    redis = FakeRedis()
    limiter = RedisTokenBucketRateLimiter(redis)
    key = rate_limit_key("tencent", "ap-guangzhou", "VatInvoiceOCR")

    first = limiter.acquire("tencent", "ap-guangzhou", "VatInvoiceOCR", qps_limit=2, now_ms=0)
    second = limiter.acquire("tencent", "ap-guangzhou", "VatInvoiceOCR", qps_limit=2, now_ms=0)
    third = limiter.acquire("tencent", "ap-guangzhou", "VatInvoiceOCR", qps_limit=2, now_ms=0)
    fourth = limiter.acquire("tencent", "ap-guangzhou", "VatInvoiceOCR", qps_limit=2, now_ms=500)

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.retry_after_seconds == 0.5
    assert fourth.allowed is True
    assert key in redis.hashes
    assert redis.expirations[key] == 2


def test_rate_limiter_uses_provider_region_and_action_in_key() -> None:
    assert rate_limit_key("tencent", "ap-guangzhou", "VatInvoiceOCR") == "ocr:rate_limit:tencent:ap-guangzhou:VatInvoiceOCR"
    assert rate_limit_key("tencent", None, "VatInvoiceOCR") == "ocr:rate_limit:tencent:global:VatInvoiceOCR"


def test_effective_qps_clamps_tencent_to_internal_default_and_configured_limit() -> None:
    assert effective_qps(SimpleNamespace(provider="tencent", qps_limit=50)) == 8
    assert effective_qps(SimpleNamespace(provider="tencent", qps_limit=5)) == 5
    assert effective_qps(SimpleNamespace(provider="mock", qps_limit=100)) == 100
    assert effective_qps(SimpleNamespace(provider="mock", qps_limit=0)) == 1
