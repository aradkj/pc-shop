"""CSRF protection for state-changing requests using cookie authentication.

Implements the standard double-submit cookie pattern. The server sets a non-HttpOnly
`csrf_token` cookie that the frontend reads and submits via the `X-CSRF-Token` header.
"""

import secrets

from fastapi import Request, Response

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str | None = None) -> str:
    settings = get_settings()
    token = token or generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,  # JavaScript must read this to send it in X-CSRF-Token header
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return token


def validate_csrf(request: Request) -> None:
    """Validate CSRF token for state-changing requests.

    Raises ForbiddenError (403) if the CSRF token cookie and header do not match.
    """
    if request.method in SAFE_METHODS:
        return

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_token or not header_token or not secrets.compare_digest(cookie_token, header_token):
        raise ForbiddenError("CSRF token missing or invalid")
