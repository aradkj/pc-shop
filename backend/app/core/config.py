"""Application settings.

Everything is read from environment variables. A `.env` file (see
`.env.example`) is loaded for local development; real environment variables
always take priority over it.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

API_V1_PREFIX = "/api/v1"

_MIN_PRODUCTION_SECRET_LENGTH = 32
_PLACEHOLDER_SECRET_PREFIX = "change-me"


class ConfigError(RuntimeError):
    """Raised when the application is misconfigured."""


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    cors_origins: tuple[str, ...]
    log_level: str
    bcrypt_rounds: int

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def has_placeholder_secret(self) -> bool:
        return self.secret_key.lower().startswith(_PLACEHOLDER_SECRET_PREFIX)


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Environment variable {name} is required (see .env.example).")
    return value


def _integer(name: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer.") from exc
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f">= {minimum}" if maximum is None else f"between {minimum} and {maximum}"
        raise ConfigError(f"Environment variable {name} must be {bounds}.")
    return value


def _csv(name: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, "").split(",") if item.strip())


@lru_cache
def get_settings() -> Settings:
    settings = Settings(
        app_env=os.getenv("APP_ENV", "development").strip().lower(),
        database_url=_required("DATABASE_URL"),
        secret_key=_required("SECRET_KEY"),
        algorithm=os.getenv("ALGORITHM", "HS256").strip(),
        access_token_expire_minutes=_integer("ACCESS_TOKEN_EXPIRE_MINUTES", 60, minimum=1),
        cors_origins=_csv("CORS_ORIGINS"),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        bcrypt_rounds=_integer("BCRYPT_ROUNDS", 12, minimum=4, maximum=31),
    )
    if settings.is_production and (
        settings.has_placeholder_secret or len(settings.secret_key) < _MIN_PRODUCTION_SECRET_LENGTH
    ):
        raise ConfigError(
            "SECRET_KEY is a placeholder or shorter than 32 characters. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    return settings
