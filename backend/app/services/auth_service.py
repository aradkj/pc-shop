import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_secure_token,
    get_dummy_hash,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.token import PasswordResetToken, RefreshToken
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)


def register_user(db: Session, data: UserCreate) -> User:
    """Create a customer account. The password is hashed before it is stored."""
    if db.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise ConflictError("Email is already registered")
    if db.scalar(select(User.id).where(User.username == data.username)) is not None:
        raise ConflictError("Username is already taken")

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # lost a race against a concurrent registration
        db.rollback()
        raise ConflictError("Email or username is already in use") from None
    db.refresh(user)
    logger.info("User registered: id=%s username=%s", user.id, user.username)
    return user


def authenticate(db: Session, identifier: str, password: str) -> User:
    """Return the user matching an email/username and password, or raise."""
    identifier = identifier.strip().lower()
    user = db.scalar(select(User).where(or_(User.email == identifier, User.username == identifier)))

    # Always run a bcrypt check so the response time does not reveal whether the account exists.
    password_ok = verify_password(password, user.hashed_password if user else get_dummy_hash())
    if user is None or not password_ok:
        # Never log the identifier: users sometimes type their password in that field.
        logger.warning("Failed login attempt (%s)", "unknown account" if user is None else f"user_id={user.id}")
        raise UnauthorizedError("Incorrect email or password")
    if not user.is_active:
        logger.warning("Login blocked for disabled account: user_id=%s", user.id)
        raise ForbiddenError("This account has been disabled")
    return user


def create_refresh_token_for_user(db: Session, user_id: int) -> str:
    settings = get_settings()
    raw_token = generate_secure_token()
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    db.add(RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at))
    db.commit()
    return raw_token


def login(db: Session, identifier: str, password: str) -> dict[str, str | int]:
    user = authenticate(db, identifier, password)
    logger.info("User logged in: id=%s", user.id)
    refresh_token = create_refresh_token_for_user(db, user.id)
    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
        "expires_in": get_settings().access_token_expire_minutes * 60,
        "refresh_token": refresh_token,
    }


def refresh_access_token(db: Session, raw_refresh_token: str) -> dict[str, str | int]:
    """Rotate refresh token and issue a fresh access token."""
    token_hash = hash_token(raw_refresh_token)
    now = datetime.now(UTC)
    record = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
    )
    if record is None:
        raise UnauthorizedError("Invalid or expired refresh token")

    # Invalidate old refresh token (rotation)
    record.revoked_at = now
    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        db.commit()
        raise ForbiddenError("This account has been disabled")

    # Create new refresh token
    new_raw_refresh = generate_secure_token()
    new_expires_at = now + timedelta(days=get_settings().refresh_token_expire_days)
    db.add(RefreshToken(user_id=user.id, token_hash=hash_token(new_raw_refresh), expires_at=new_expires_at))
    db.commit()

    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
        "expires_in": get_settings().access_token_expire_minutes * 60,
        "refresh_token": new_raw_refresh,
    }


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    token_hash = hash_token(raw_refresh_token)
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if record and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        db.commit()


def revoke_all_user_sessions(db: Session, user_id: int) -> None:
    now = datetime.now(UTC)
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise BadRequestError("Incorrect current password")

    user.hashed_password = hash_password(new_password)
    # Invalidate all existing refresh sessions
    revoke_all_user_sessions(db, user.id)
    db.commit()
    logger.info("Password changed for user_id=%s", user.id)


def initiate_password_reset(db: Session, email: str) -> str | None:
    """Initiates a password reset. Never reveals whether email exists."""
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active:
        # constant timing check
        verify_password("dummy", get_dummy_hash())
        return None

    raw_token = generate_secure_token()
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    db.add(PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    db.commit()
    logger.info("Password reset initiated for user_id=%s", user.id)
    return raw_token


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    token_hash = hash_token(raw_token)
    now = datetime.now(UTC)
    record = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )
    if record is None:
        raise BadRequestError("Invalid or expired password reset token")

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise BadRequestError("Invalid or expired password reset token")

    user.hashed_password = hash_password(new_password)
    record.used_at = now
    # Invalidate all active sessions for the user
    revoke_all_user_sessions(db, user.id)
    db.commit()
    logger.info("Password successfully reset for user_id=%s", user.id)
