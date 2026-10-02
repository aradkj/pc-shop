import logging

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.user import User

logger = logging.getLogger(__name__)


def get_stats(db: Session) -> dict[str, int]:
    """Counters for the admin dashboard."""

    def count(model, *conditions) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0

    return {
        "total_products": count(Product),
        "total_orders": count(Order),
        "total_users": count(User),
        "pending_orders": count(Order, Order.status == OrderStatus.PENDING),
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

    user.is_active = is_active
    db.commit()
    db.refresh(user)
    logger.info("User %s by admin_id=%s: user_id=%s", "enabled" if is_active else "disabled", admin.id, user.id)
    return user
