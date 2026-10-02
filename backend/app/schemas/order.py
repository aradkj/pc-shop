from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.order import OrderStatus
from app.schemas.common import Money
from app.schemas.user import UserBrief


class OrderItemRead(BaseModel):
    """A purchased line. `product_name` / `unit_price` are the values at purchase time."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None
    product_name: str
    unit_price: Money
    quantity: int
    subtotal: Money


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    total_price: Money
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


class AdminOrderRead(OrderRead):
    user: UserBrief


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
