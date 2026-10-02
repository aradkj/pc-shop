from pydantic import BaseModel


class AdminStats(BaseModel):
    total_products: int
    total_orders: int
    total_users: int
    pending_orders: int


class UserActiveUpdate(BaseModel):
    is_active: bool
