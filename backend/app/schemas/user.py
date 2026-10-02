from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.models.user import UserRole

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$"),
]


class UserCreate(BaseModel):
    """Payload of `POST /auth/register`. The role is never client-controlled."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "user@example.com",
                    "username": "user123",
                    "password": "Password123!",
                    "first_name": "John",
                    "last_name": "Doe",
                }
            ]
        }
    )

    email: EmailStr
    username: Username
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)
    first_name: Name
    last_name: Name

    @field_validator("email", "username")
    @classmethod
    def _lowercase(cls, value: str) -> str:
        # Emails and usernames are case-insensitive: store them lowercased.
        return value.lower()

    @field_validator("password")
    @classmethod
    def _password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes long")
        return value


class UserRead(BaseModel):
    """Public representation of a user. Never contains the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserBrief(BaseModel):
    """Minimal user info embedded in admin order views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    first_name: str
    last_name: str
