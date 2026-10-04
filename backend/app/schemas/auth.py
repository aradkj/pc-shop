from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.security import MAX_PASSWORD_BYTES



class AuthResponse(BaseModel):
    """Metadata response for cookie-based authentication."""

    authenticated: bool = True
    expires_in: int = Field(description="Token lifetime in seconds")


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes long")
        return value

    @model_validator(mode="after")
    def _passwords_match(self) -> "ChangePassword":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match")
        return self


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes long")
        return value

    @model_validator(mode="after")
    def _passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match")
        return self


class MessageResponse(BaseModel):
    detail: str
