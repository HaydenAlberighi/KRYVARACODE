"""In-memory sliding-window rate limiting (skeleton grade).

The default settings keep rate limiting disabled (``RATE_LIMIT_ENABLED=false``).
When enabled, a process-local ``RateLimiter`` guards the API by client IP with a
fixed-window-within-sliding check.  A Redis-backed distributed limiter can replace
this module later without touching the middleware contract.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.core.config import settings


def parse_rate_limit(value: str) -> tuple[int, int]:
    """Parse a ``"<count>/<unit>"`` string (e.g. ``"100/minute"``) into ``(count, window_seconds)``.

    Raises ``ValueError`` for malformed input.
    """
    count_str, _, unit = value.strip().lower().partition("/")
    if not count_str or not unit:
        raise ValueError(f"Invalid rate limit format: {value!r} (expected '<count>/<unit>')")
    count = int(count_str)
    unit_seconds = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
    }
    # Accept singular/plural unit names.
    window = unit_seconds.get(unit) or unit_seconds.get(unit[:-1])
    if window is None:
        raise ValueError(f"Unsupported rate limit unit: {unit!r}")
    if count <= 0:
        raise ValueError("Rate limit count must be positive")
    return count, window


class RateLimiter:
    """Sliding-window limiter backed by per-key monotonic-timestamp deques."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Return True if a request for ``key`` is within the budget."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def _build_rate_limiter() -> RateLimiter | None:
    """Build the process limiter from settings, or ``None`` when disabled."""
    if not settings.RATE_LIMIT_ENABLED:
        return None
    limit, window = parse_rate_limit(settings.RATE_LIMIT_DEFAULT)
    return RateLimiter(limit=limit, window=float(window))


#: Process-wide limiter; ``None`` unless rate limiting is enabled in settings.
rate_limiter = _build_rate_limiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests past the budget with a structured 429 response."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        if request.method == "OPTIONS" or request.url.path in (
            "/health",
            "/api/v1/metrics",
        ):
            return await call_next(request)  # type: ignore[no-any-return]

        if rate_limiter is None:
            return await call_next(request)  # type: ignore[no-any-return]

        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.allow(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Try again shortly.",
                    "error_code": "rate_limit_exceeded",
                    "status_code": 429,
                },
                headers={"Retry-After": str(int(rate_limiter.window))},
            )
        return await call_next(request)  # type: ignore[no-any-return]
