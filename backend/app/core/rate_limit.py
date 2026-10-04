"""Lightweight in-memory IP-based rate limiter.

Designed to prevent brute-force attacks on sensitive endpoints (login, register, password reset)
with support for Retry-After headers, independent client IPs, and resetting on successful auth.
Can easily be swapped with a Redis-backed implementation in distributed deployments.
"""
from fastapi import Request
import threading
import time
from collections import defaultdict
from app.core.exceptions import TooManyRequestsError


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # key -> list of float timestamps
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "127.0.0.1"

    def check(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        """Check if `key` has exceeded `limit` hits within `window_seconds`.

        Returns `(allowed, retry_after)`. Does not record a hit.
        """
        now = time.monotonic()
        with self._lock:
            timestamps = self._hits[key]
            # Prune old timestamps
            self._hits[key] = [t for t in timestamps if now - t < window_seconds]
            current_count = len(self._hits[key])
            if current_count >= limit:
                oldest = self._hits[key][0]
                retry_after = max(1, int(window_seconds - (now - oldest)))
                return False, retry_after
            return True, 0

    def record(self, key: str) -> None:
        """Record a hit for `key`."""
        now = time.monotonic()
        with self._lock:
            self._hits[key].append(now)

    def reset(self, key: str) -> None:
        """Reset hit count for `key` (e.g. upon successful authentication)."""
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        """Clear all keys (useful for testing)."""
        with self._lock:
            self._hits.clear()

    def enforce(self, request: Request, scope: str, limit: int, window_seconds: int = 60) -> None:
        """Enforce rate limit for the client IP in given scope.

        Raises `RateLimitExceededError` if exceeded, otherwise records the attempt.
        """
        ip = self._get_client_ip(request)
        key = f"{scope}:{ip}"
        allowed, retry_after = self.check(key, limit, window_seconds)
        if not allowed:
            raise TooManyRequestsError(retry_after=retry_after)
        self.record(key)

    def get_ip_scope_key(self, request: Request, scope: str) -> str:
        ip = self._get_client_ip(request)
        return f"{scope}:{ip}"


limiter = InMemoryRateLimiter()
