"""Rate limiting middleware.

Uses a simple in-memory token bucket per client IP.
For production, consider redis-backed rate limiting.
"""
import os
import time
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Configuration
RATE_LIMIT_ENABLED = os.getenv("COCO_RATE_LIMIT", "true").lower() in ("true", "1", "yes")
RATE_LIMIT_RPM = int(os.getenv("COCO_RATE_LIMIT_RPM", "120"))  # requests per minute
RATE_LIMIT_BURST = int(os.getenv("COCO_RATE_LIMIT_BURST", "20"))  # burst allowance

# Paths exempt from rate limiting
EXEMPT_PATHS = {
    "/api/health",
    "/api/events",  # SSE — long-lived connections
    "/api/edition",
}


class TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, rate: float, burst: int):
        self.rate = rate  # tokens per second
        self.burst = burst
        self.tokens: dict[str, float] = defaultdict(lambda: float(burst))
        self.last_refill: dict[str, float] = defaultdict(time.monotonic)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill[key]
        self.last_refill[key] = now

        # Refill tokens
        self.tokens[key] = min(
            self.burst,
            self.tokens[key] + elapsed * self.rate,
        )

        # Consume a token
        if self.tokens[key] >= 1.0:
            self.tokens[key] -= 1.0
            return True
        return False

    def cleanup(self, max_age: float = 300.0):
        """Remove stale entries older than max_age seconds."""
        now = time.monotonic()
        stale = [k for k, t in self.last_refill.items() if now - t > max_age]
        for k in stale:
            del self.tokens[k]
            del self.last_refill[k]


# Global bucket instance
_bucket = TokenBucket(rate=RATE_LIMIT_RPM / 60.0, burst=RATE_LIMIT_BURST)
_cleanup_counter = 0


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For if behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        global _cleanup_counter

        if not RATE_LIMIT_ENABLED:
            return await call_next(request)

        path = request.url.path

        # Exempt paths
        if path in EXEMPT_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        client_ip = _get_client_ip(request)

        if not _bucket.allow(client_ip):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please slow down.",
                headers={"Retry-After": "5"},
            )

        # Periodic cleanup (every 100 requests)
        _cleanup_counter += 1
        if _cleanup_counter >= 100:
            _cleanup_counter = 0
            _bucket.cleanup()

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_RPM)
        return response
