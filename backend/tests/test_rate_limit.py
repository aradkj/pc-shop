import pytest
from app.core.rate_limit import InMemoryRateLimiter, limiter

AUTH_URL = "/api/v1/auth"


def test_in_memory_rate_limiter_unit():
    rl = InMemoryRateLimiter()
    # 3 hits allowed per 10 seconds
    for _ in range(3):
        allowed, retry = rl.check("test-key", limit=3, window_seconds=10)
        assert allowed is True
        rl.record("test-key")

    # 4th hit should be blocked
    allowed, retry = rl.check("test-key", limit=3, window_seconds=10)
    assert allowed is False
    assert retry > 0

    # Reset clears hits
    rl.reset("test-key")
    allowed, _ = rl.check("test-key", limit=3, window_seconds=10)
    assert allowed is True


def test_rate_limit_exceeded_returns_429_and_retry_after(client):
    from app.core.config import get_settings
    settings = get_settings()
    limit = settings.rate_limit_login_per_minute  # 5 by default

    # Exhaust the limit
    for _ in range(limit):
        res = client.post(f"{AUTH_URL}/login", data={"username": "nobody", "password": "wrong"})
        assert res.status_code == 401

    # Next request should return 429
    res = client.post(f"{AUTH_URL}/login", data={"username": "nobody", "password": "wrong"})
    assert res.status_code == 429
    assert "Too many requests" in res.json()["detail"]
    assert "Retry-After" in res.headers

