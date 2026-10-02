from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money

MAX_ITEM_QUANTITY = 100


class CartItemCreate(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(default=1, ge=1, le=MAX_ITEM_QUANTITY)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=MAX_ITEM_QUANTITY)


class CartProduct(BaseModel):
    """The product fields a cart row needs to render itself (current values)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    price: Money
    stock: int
    image_url: str | None
    brand: str | None
    is_active: bool


class CartItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    quantity: int
    product: CartProduct
    subtotal: Money


class CartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    items: list[CartItemRead]
    total_items: int = Field(description="Sum of all item quantities")
    total_price: Money
