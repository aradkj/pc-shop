"""Password hashing (bcrypt) and JWT helpers."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

import bcrypt
import jwt

from app.core.config import get_settings

# bcrypt only looks at the first 72 bytes of a password.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash for `password`."""
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Check `password` against a bcrypt hash without ever raising."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:  # malformed hash or over-long password
        return False


@lru_cache
def get_dummy_hash() -> str:
    """A valid hash used to keep login timing constant for unknown accounts."""
    return hash_password("this-is-not-a-real-password")


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT carrying `sub` (user id), `iat` and `exp`."""
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload = {"sub": subject, "iat": now, "exp": expires}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str:
    """Validate a JWT and return its subject.

    Raises `jwt.PyJWTError` if the token is malformed, expired or has a bad
    signature. Only the configured algorithm is accepted.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        options={"require": ["exp", "sub"]},
    )
    return payload["sub"]
