from decimal import Decimal
from typing import Any
from pydantic import BaseModel, Field

from app.schemas.common import Money


class CompatibilityIssue(BaseModel):
    type: str
    severity: str = "error"  # "error", "warning", "info"
    components: list[str]
    message: str


class RecommendationItem(BaseModel):
    type: str
    category: str
    match_level: str  # "recommended", "good match", "not ideal"
    message: str


class BuilderProductBrief(BaseModel):
    id: int
    name: str
    slug: str
    brand: str | None = None
    price: Money
    stock: int
    is_active: bool = True
    category_slug: str
    image_url: str | None = None
    specifications: dict[str, Any] | None = None


class BuildValidationRequest(BaseModel):
    components: dict[str, int] = Field(
        default_factory=dict,
        description="Map of category slug (e.g. 'cpu', 'motherboard') to product ID",
    )
    product_ids: list[int] = Field(
        default_factory=list,
        description="Optional list of product IDs across the build",
    )


class BuildValidationResponse(BaseModel):
    compatible: bool
    complete: bool
    issues: list[CompatibilityIssue] = Field(default_factory=list)
    warnings: list[CompatibilityIssue] = Field(default_factory=list)
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    selected_products: dict[str, BuilderProductBrief] = Field(default_factory=dict)
    subtotal: Money = Decimal("0.00")
    discount_percent: Decimal = Decimal("0")
    discount_amount: Money = Decimal("0.00")
    total: Money = Decimal("0.00")


class GPURecommendation(BaseModel):
    product_id: int
    name: str
    brand: str | None = None
    price: Money
    stock: int
    score: int
    match_level: str  # "recommended", "good match", "not ideal"
    reason: str
    specifications: dict[str, Any] | None = None


class BuilderOptionsResponse(BaseModel):
    categories: list[str]
    options: dict[str, list[BuilderProductBrief]]


class AddBuildToCartRequest(BaseModel):
    components: dict[str, int] = Field(
        default_factory=dict,
        description="Map of category slug to product ID",
    )
    product_ids: list[int] = Field(
        default_factory=list,
        description="Optional list of product IDs",
    )
    clear_existing: bool = False
