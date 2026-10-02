from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession
from app.api.responses import AUTH_RESPONSES, CONFLICT
from app.schemas.auth import Token
from app.schemas.common import ErrorResponse
from app.schemas.user import UserCreate, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a customer account",
    responses=CONFLICT,
)
def register(data: UserCreate, db: DbSession):
    """Create a new customer account. Email and username must be unique (case-insensitive)."""
    return auth_service.register_user(db, data)


@router.post(
    "/login",
    response_model=Token,
    summary="Log in and get an access token",
    responses={
        401: {"model": ErrorResponse, "description": "Incorrect credentials"},
        403: {"model": ErrorResponse, "description": "The account is disabled"},
    },
)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """OAuth2 password flow (form-encoded).

    Send `username` - your **email address or username** - and `password`.
    Use the returned token as `Authorization: Bearer <access_token>`.
    """
    return auth_service.login(db, form.username, form.password)


@router.get("/me", response_model=UserRead, summary="Get the current user", responses=AUTH_RESPONSES)
def read_current_user(user: CurrentUser):
    return user
