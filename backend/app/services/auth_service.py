import logging

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import create_access_token, get_dummy_hash, hash_password, verify_password
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


def login(db: Session, identifier: str, password: str) -> dict[str, str | int]:
    user = authenticate(db, identifier, password)
    logger.info("User logged in: id=%s", user.id)
    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
        "expires_in": get_settings().access_token_expire_minutes * 60,
    }
