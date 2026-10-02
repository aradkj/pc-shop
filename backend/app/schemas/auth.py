from pydantic import BaseModel, Field


class Token(BaseModel):
    """OAuth2-compatible login response."""

    access_token: str
    token_type: str = Field(default="bearer", examples=["bearer"])
    expires_in: int = Field(description="Token lifetime in seconds")
