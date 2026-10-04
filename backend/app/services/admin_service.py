import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.services import audit_service

logger = logging.getLogger(__name__)


def get_stats(db: Session) -> dict[str, Any]:
    """Counters and metrics for the admin dashboard using efficient SQL aggregates."""
    # Group order counts by status in a single query
    status_counts = dict(
        db.execute(
            select(Order.status, func.count(Order.id)).group_by(Order.status)
        ).all()
    )
    total_orders = sum(status_counts.values())
    pending_orders = status_counts.get(OrderStatus.PENDING, 0)
    processing_orders = status_counts.get(OrderStatus.PROCESSING, 0)
    shipped_orders = status_counts.get(OrderStatus.SHIPPED, 0)
    completed_orders = status_counts.get(OrderStatus.COMPLETED, 0)
    cancelled_orders = status_counts.get(OrderStatus.CANCELLED, 0)

    # Total revenue from non-cancelled orders using SQL SUM
    total_revenue = db.scalar(
        select(func.coalesce(func.sum(Order.total_price), Decimal("0.00")))
        .where(Order.status != OrderStatus.CANCELLED)
    ) or Decimal("0.00")

    # Product counts and low-stock count (stock <= 5 and active) using SQL COUNT
    total_products = db.scalar(select(func.count(Product.id))) or 0
    low_stock_products = db.scalar(
        select(func.count(Product.id)).where(Product.stock <= 5, Product.is_active.is_(True))
    ) or 0

    total_users = db.scalar(select(func.count(User.id))) or 0

    return {
        "total_products": total_products,
        "total_orders": total_orders,
        "total_users": total_users,
        "pending_orders": pending_orders,
        "processing_orders": processing_orders,
        "shipped_orders": shipped_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "total_revenue": total_revenue,
        "low_stock_products": low_stock_products,
    }



def list_users(db: Session, *, search: str | None, page: int, limit: int) -> tuple[list[User], int]:
    conditions = []
    if search and search.strip():
        escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(
                User.email.ilike(pattern, escape="\\"),
                User.username.ilike(pattern, escape="\\"),
                User.first_name.ilike(pattern, escape="\\"),
                User.last_name.ilike(pattern, escape="\\"),
            )
        )
    total = db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0
    stmt = select(User).where(*conditions).order_by(User.id).offset((page - 1) * limit).limit(limit)
    return list(db.scalars(stmt)), total


def set_user_active(db: Session, admin: User, user_id: int, is_active: bool) -> User:
    """Enable or disable an account. Disabled users can no longer log in or use their token."""
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if user.id == admin.id and not is_active:
        raise BadRequestError("You cannot disable your own account")

    old_active = user.is_active
    user.is_active = is_active

    action = "USER_ENABLED" if is_active else "USER_DISABLED"
    audit_service.record_audit_log(
        db,
        admin_user_id=admin.id,
        action=action,
        entity_type="user",
        entity_id=user.id,
        old_value={"is_active": old_active},
        new_value={"is_active": is_active},
    )

    db.commit()
    db.refresh(user)

    logger.info("User %s by admin_id=%s: user_id=%s", "enabled" if is_active else "disabled", admin.id, user.id)
    return user
