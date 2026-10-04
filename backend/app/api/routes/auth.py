from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.api.responses import AUTH_RESPONSES, CONFLICT
from app.core.config import get_settings
from app.core.csrf import generate_csrf_token, set_csrf_cookie
from app.core.exceptions import UnauthorizedError
from app.core.rate_limit import limiter
from app.schemas.auth import (
    AuthResponse,
    ChangePassword,
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
)
from app.schemas.common import ErrorResponse
from app.schemas.user import UserCreate, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str | None = None) -> None:
    settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
        max_age=settings.access_token_expire_minutes * 60,
    )
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
            path="/",
            max_age=settings.refresh_token_expire_days * 86400,
        )
    set_csrf_cookie(response)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="csrf_token", path="/")


@router.get("/csrf", response_model=dict[str, str], summary="Get CSRF token")
def get_csrf(response: Response):
    """Retrieve a CSRF token and set the csrf_token cookie for double-submit protection."""
    token = set_csrf_cookie(response)
    return {"csrf_token": token}


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a customer account",
    responses=CONFLICT,
)
def register(data: UserCreate, request: Request, response: Response, db: DbSession):
    """Create a new customer account. Email and username must be unique (case-insensitive)."""
    settings = get_settings()
    limiter.enforce(request, "register", settings.rate_limit_register_per_minute, window_seconds=60)
    user = auth_service.register_user(db, data)
    set_csrf_cookie(response)
    return user


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Log in and receive HttpOnly authentication cookies",
    responses={
        401: {"model": ErrorResponse, "description": "Incorrect credentials"},
        403: {"model": ErrorResponse, "description": "The account is disabled"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    response: Response,
    db: DbSession,
):
    """OAuth2 password flow. Sets HttpOnly cookies and returns safe metadata only."""
    settings = get_settings()
    limiter.enforce(request, "login", settings.rate_limit_login_per_minute, window_seconds=60)
    login_data = auth_service.login(db, form.username, form.password)

    # Clear rate limit hits on successful login for this client IP
    login_key = limiter.get_ip_scope_key(request, "login")
    limiter.reset(login_key)

    _set_auth_cookies(response, str(login_data["access_token"]), str(login_data.get("refresh_token")))
    return AuthResponse(authenticated=True, expires_in=int(login_data["expires_in"]))


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Refresh access token using refresh_token cookie",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
    },
)
def refresh(request: Request, response: Response, db: DbSession):
    """Rotate the refresh token and return safe metadata, updating cookies."""
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        raise UnauthorizedError("Missing refresh token")

    token_data = auth_service.refresh_access_token(db, raw_refresh)
    _set_auth_cookies(response, str(token_data["access_token"]), str(token_data.get("refresh_token")))
    return AuthResponse(authenticated=True, expires_in=int(token_data["expires_in"]))


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out and clear authentication cookies",
)
def logout(request: Request, response: Response, db: DbSession):
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        auth_service.revoke_refresh_token(db, raw_refresh)
    _clear_auth_cookies(response)
    return {"detail": "Logged out successfully"}


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change password for current user",
    responses=AUTH_RESPONSES,
)
def change_password_endpoint(
    data: ChangePassword,
    user: CurrentUser,
    response: Response,
    db: DbSession,
):
    auth_service.change_password(db, user, data.current_password, data.new_password)
    # Issue fresh refresh token & access token for the updated session
    new_refresh = auth_service.create_refresh_token_for_user(db, user.id)
    new_access = auth_service.create_access_token(str(user.id))
    _set_auth_cookies(response, new_access, new_refresh)
    return {"detail": "Password changed successfully"}


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Initiate password reset (does not reveal if email exists)",
)
def forgot_password_endpoint(
    data: ForgotPasswordRequest,
    request: Request,
    db: DbSession,
):
    settings = get_settings()
    limiter.enforce(request, "reset", settings.rate_limit_reset_per_minute, window_seconds=60)
    auth_service.initiate_password_reset(db, data.email)
    return {"detail": "If the account exists, a password reset process has been initiated."}


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password with reset token",
)
def reset_password_endpoint(
    data: ResetPasswordRequest,
    request: Request,
    db: DbSession,
):
    settings = get_settings()
    limiter.enforce(request, "reset", settings.rate_limit_reset_per_minute, window_seconds=60)
    auth_service.reset_password(db, data.token, data.new_password)
    return {"detail": "Password has been reset successfully. You can now log in."}


@router.get("/me", response_model=UserRead, summary="Get the current user", responses=AUTH_RESPONSES)
def read_current_user(user: CurrentUser, response: Response):
    set_csrf_cookie(response)
    return user
