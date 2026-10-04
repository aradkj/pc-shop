"""Building blocks shared by several schemas."""

from decimal import Decimal
from math import ceil
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, Field, PlainSerializer

T = TypeVar("T")

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

# Money is a `Decimal` everywhere (database, services, schemas) and serialized
# to JSON as an exact 2-decimal string representation (e.g. "599.99") to prevent
# binary floating-point inaccuracy.
def serialize_money(v: Decimal | float | int | str) -> str:
    if not isinstance(v, Decimal):
        v = Decimal(str(v))
    return f"{v:.2f}"


Money = Annotated[Decimal, PlainSerializer(serialize_money, return_type=str, when_used="json")]


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
