"""ASGI middlewares: per-request correlation IDs and baseline security headers.

- ``RequestContextMiddleware`` assigns every request a ``request_id`` (used by
  the logging filter), echoes it in an ``X-Request-ID`` response header, and
  accepts a matching inbound header so traces can be correlated in/out.
- ``SecurityHeadersMiddleware`` adds defensive security headers to every
  response unless a route already set a stricter value.
"""

import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.logging_setup import request_id_var

MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns and tracks the ``request_id`` ContextVar for one request."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        header_value = request.headers.get("x-request-id", "")
        try:
            request_id = str(uuid.UUID(header_value))
        except (ValueError, AttributeError):
            request_id = str(uuid.uuid4())

        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)

        response.headers["X-Request-ID"] = request_id
        return response


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Rejects cookie-authenticated state-changing requests without the CSRF header.

    SameSite=Lax stops the cookie from attaching to cross-site mutating
    requests in all modern browsers, and a cross-site attacker cannot set a
    custom ``X-CSRF-Protected`` header without a CORS preflight (our CORS is
    same-origin only). This custom-header check is the belt-and-suspenders
    layer on top of SameSite. Requests authenticated purely via the
    ``Authorization`` header do not need the header (tests use that path).
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if (
            request.method in MUTATING_METHODS
            and settings.cookie_name in request.cookies
            and request.headers.get(settings.csrf_header) != settings.csrf_header_value
        ):
            return Response(status_code=403, content="CSRF check failed")
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers; routes may override with stricter values."""

    CSP = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        header_defaults = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            "Content-Security-Policy": self.CSP,
        }
        for name, value in header_defaults.items():
            response.headers.setdefault(name, value)
        return response