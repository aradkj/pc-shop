"""Reusable FastAPI dependencies: database session, authentication, authorization."""

from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import API_V1_PREFIX
from app.core.csrf import validate_csrf
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User

# Makes the "Authorize" button of /docs work with the OAuth2 login endpoint.
# auto_error=False allows checking cookies when no Authorization header is sent.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{API_V1_PREFIX}/auth/login", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    request: Request,
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> User:
    """Resolve authentication via Bearer token header OR HttpOnly access_token cookie."""
    is_cookie_auth = False
    raw_token = token

    if not raw_token:
        raw_token = request.cookies.get("access_token")
        if raw_token:
            is_cookie_auth = True

    if not raw_token:
        raise UnauthorizedError("Not authenticated")

    # If authenticated via cookie on state-changing request, enforce CSRF
    if is_cookie_auth:
        validate_csrf(request)

    try:
        user_id = int(decode_access_token(raw_token))
    except (jwt.PyJWTError, ValueError):
        raise UnauthorizedError("Invalid or expired token") from None

    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("Invalid or expired token")
    if not user.is_active:
        raise ForbiddenError("This account has been disabled")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Allow only admins (403 for everybody else)."""
    if not user.is_admin:
        raise ForbiddenError("Admin privileges required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
