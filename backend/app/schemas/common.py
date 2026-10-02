"""Building blocks shared by several schemas."""

from decimal import Decimal
from math import ceil
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, Field, PlainSerializer

T = TypeVar("T")

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

# Money is a `Decimal` everywhere (database, services, schemas) so arithmetic is
# exact. Only the JSON representation is a plain number, e.g. 599.99.
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]

# A price accepted from a client: non-negative, at most 2 decimals, matches Numeric(12, 2).
PriceInput = Annotated[Decimal, Field(ge=0, le=Decimal("1000000"), max_digits=12, decimal_places=2)]


class ErrorResponse(BaseModel):
    detail: str = Field(examples=["Resource not found"])


class Page(BaseModel, Generic[T]):
    """Envelope returned by every paginated endpoint."""

    items: list[T]
    total: int = Field(description="Total number of items matching the query")
    page: int = Field(description="Current page (1-based)")
    limit: int = Field(description="Maximum number of items per page")
    pages: int = Field(description="Total number of pages")


def build_page(items: list[Any], total: int, page: int, limit: int) -> dict[str, Any]:
    return {"items": items, "total": total, "page": page, "limit": limit, "pages": ceil(total / limit)}
