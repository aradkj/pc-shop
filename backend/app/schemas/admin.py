from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Money


class AdminStats(BaseModel):
    total_products: int
    total_orders: int
    total_users: int
    pending_orders: int
    processing_orders: int = 0
    shipped_orders: int = 0
    completed_orders: int = 0
    cancelled_orders: int = 0
    total_revenue: Money = Decimal("0.00")
    low_stock_products: int = 0


class UserActiveUpdate(BaseModel):
    is_active: bool



class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_user_id: int | None
    action: str
    entity_type: str
    entity_id: str | None
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    created_at: datetime
