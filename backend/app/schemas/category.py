from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.common import SLUG_PATTERN

CategoryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
Slug = Annotated[str, StringConstraints(min_length=1, max_length=120, pattern=SLUG_PATTERN)]


class CategoryCreate(BaseModel):
    name: CategoryName
    slug: Slug | None = Field(default=None, description="Generated from the name when omitted")
    description: str | None = Field(default=None, max_length=2000)


class CategoryUpdate(BaseModel):
    name: CategoryName | None = None
    slug: Slug | None = None
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _required_columns_not_null(self) -> Self:
        for field in ("name", "slug"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    created_at: datetime


class CategoryBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
