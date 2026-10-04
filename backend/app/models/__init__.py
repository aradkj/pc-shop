"""Import every model so `Base.metadata` is complete (needed by Alembic)."""

from app.models.audit_log import AuditLog
from app.models.cart import Cart, CartItem
from app.models.category import Category
from app.models.order import ALLOWED_ORDER_TRANSITIONS, Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.token import PasswordResetToken, RefreshToken
from app.models.user import User, UserRole

__all__ = [
    "ALLOWED_ORDER_TRANSITIONS",
    "AuditLog",
    "Cart",
    "CartItem",
    "Category",
    "Order",
    "OrderItem",
    "OrderStatus",
    "PasswordResetToken",
    "Product",
    "RefreshToken",
    "User",
    "UserRole",
]
