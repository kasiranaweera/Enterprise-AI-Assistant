"""
Token bucket rate limiter, per-user, in-process.

For a single backend replica this in-memory dict is fine for a POC.
For multi-replica production you'd back this with Redis (INCR + TTL,
or a Lua script for atomicity) — noted in README as a scale trade-off.
"""
import asyncio
import time

from backend.app.config import get_settings

settings = get_settings()


class TokenBucket:
    def __init__(self, capacity: float, refill_per_sec: float):
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def try_consume(self, cost: float = 1.0) -> tuple[bool, float]:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
            self.last_refill = now

            if self.tokens >= cost:
                self.tokens -= cost
                return True, 0.0

            deficit = cost - self.tokens
            retry_after = (deficit / self.refill_per_sec) if self.refill_per_sec > 0 else float("inf")
            return False, retry_after


class RateLimiterRegistry:
    """Holds one bucket per user, created lazily."""

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def get_bucket(self, user_key: str) -> TokenBucket:
        async with self._lock:
            if user_key not in self._buckets:
                self._buckets[user_key] = TokenBucket(
                    capacity=settings.rate_limit_capacity,
                    refill_per_sec=settings.rate_limit_refill_per_sec,
                )
            return self._buckets[user_key]

    async def check(self, user_key: str, cost: float = 1.0) -> tuple[bool, float]:
        bucket = await self.get_bucket(user_key)
        return await bucket.try_consume(cost)


rate_limiter_registry = RateLimiterRegistry()


async def enforce_rate_limit(user) -> None:
    """FastAPI dependency: raises 429 with a Retry-After-style detail if
    the caller's bucket is empty. Applied to every tool-invocation route
    (search, python-analysis, MCP, analytics) as well as chat, so a
    single "check rate limit at the top of chat" isn't the only gate —
    the spec calls out per-user limits with graceful error handling
    across tool execution generally, not just the chat endpoint.
    """
    from fastapi import HTTPException, status

    allowed, retry_after = await rate_limiter_registry.check(user.username)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry after {retry_after:.1f}s",
        )
