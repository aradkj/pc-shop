from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.schemas.category import CategoryBrief
from app.schemas.common import SLUG_PATTERN, Money, PriceInput

ProductName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
ProductSlug = Annotated[str, StringConstraints(min_length=1, max_length=220, pattern=SLUG_PATTERN)]
Brand = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

MAX_STOCK = 1_000_000


def _validate_image_url(value: str | None) -> str | None:
    """Accept http(s) URLs or a site-relative path; reject anything else (e.g. javascript:)."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("//") or not value.startswith(("http://", "https://", "/")):
        raise ValueError("image_url must be an http(s) URL or a path starting with '/'")
    return value


class ProductCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "ASUS Dual GeForce RTX 4070 Super 12GB",
                    "description": "Compact 2-slot graphics card.",
                    "price": 599.99,
                    "stock": 12,
                    "brand": "ASUS",
                    "image_url": "https://example.com/rtx-4070-super.png",
                    "category_id": 1,
                    "is_active": True,
                }
            ]
        }
    )

    name: ProductName
    slug: ProductSlug | None = Field(default=None, description="Generated from the name when omitted")
    description: str | None = Field(default=None, max_length=5000)
    price: PriceInput
    stock: int = Field(default=0, ge=0, le=MAX_STOCK)
    brand: Brand | None = None
    image_url: str | None = Field(default=None, max_length=500)
    category_id: int = Field(ge=1)
    is_active: bool = True

    _check_image_url = field_validator("image_url")(_validate_image_url)


class ProductUpdate(BaseModel):
    """Partial update: only the fields present in the request body are changed."""

    name: ProductName | None = None
    slug: ProductSlug | None = None
    description: str | None = Field(default=None, max_length=5000)
    price: PriceInput | None = None
    stock: int | None = Field(default=None, ge=0, le=MAX_STOCK)
    brand: Brand | None = None
    image_url: str | None = Field(default=None, max_length=500)
    category_id: int | None = Field(default=None, ge=1)
    is_active: bool | None = None

    _check_image_url = field_validator("image_url")(_validate_image_url)

    @model_validator(mode="after")
    def _required_columns_not_null(self) -> Self:
        for field in ("name", "slug", "price", "stock", "category_id", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    price: Money
    stock: int
    image_url: str | None
    brand: str | None
    category_id: int
    category: CategoryBrief
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductSort(StrEnum):
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    NAME = "name"


class ProductFilters(BaseModel):
    """Query parameters of the product listing endpoints."""

    search: str | None = Field(default=None, max_length=100, description="Words to look for in name, brand or description")
    category: str | None = Field(default=None, max_length=120, description="Category slug")
    category_id: int | None = Field(default=None, ge=1, description="Category id")
    brand: str | None = Field(default=None, max_length=100, description="Exact brand (case-insensitive)")
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    sort: ProductSort = ProductSort.NEWEST
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=12, ge=1, le=100)

    @model_validator(mode="after")
    def _price_range_is_valid(self) -> Self:
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("min_price cannot be greater than max_price")
        return self
