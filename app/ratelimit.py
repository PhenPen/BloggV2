"""In-memory sliding-window rate limiter for the auth endpoints.

Single-process only: counters live in process memory, so they reset on restart
and are not shared across multiple uvicorn workers. A one-worker Docker
deployment is within that contract; the upgrade path is a Redis-backed limiter.
"""

import asyncio
import time

from fastapi import HTTPException, Request, status

from app.config import settings


class SlidingWindowLimiter:
    """Allows ``max_requests`` events per ``window_seconds`` per key."""

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            timestamps = [
                stamp
                for stamp in self._hits.get(key, [])
                if now - stamp < self.window_seconds
            ]
            if len(timestamps) >= self.max_requests:
                self._hits[key] = timestamps
                return False
            timestamps.append(now)
            self._hits[key] = timestamps
            return True


async def login_rate_limit(request: Request) -> None:
    form = await request.form()
    key = f"{request.client.host}:{form.get('username', '')}"
    if await _login_limiter.allow(key):
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many login attempts. Please try again later.",
    )


async def password_reset_rate_limit(request: Request) -> None:
    key = f"{request.client.host}"
    try:
        body = await request.json()
        email = body.get("email")
        if email:
            key = f"{request.client.host}:{str(email).lower()}"
    except Exception:
        pass
    if await _email_limiter.allow(key):
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many reset requests. Please try again later.",
    )


_login_limiter = SlidingWindowLimiter(settings.rate_limit_login_per_minute)
_email_limiter = SlidingWindowLimiter(settings.rate_limit_reset_per_minute)