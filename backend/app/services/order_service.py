import logging
from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import ColumnElement, delete, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.cart import Cart, CartItem
from app.models.order import ALLOWED_ORDER_TRANSITIONS, Order, OrderStatus
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.services import audit_service

logger = logging.getLogger(__name__)


def _lock_products(db: Session, product_ids: Iterable[int]) -> dict[int, Product]:
    """Lock product rows (`SELECT ... FOR UPDATE`) and return them by id.

    Rows are locked in id order so two concurrent transactions can never
    deadlock, and `populate_existing` guarantees we see the values committed by
    a transaction we had to wait for.
    """
    stmt = (
        select(Product)
        .where(Product.id.in_(set(product_ids)))
        .options(selectinload(Product.category))
        .order_by(Product.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return {product.id: product for product in db.scalars(stmt)}


def create_order(db: Session, user: User, order_number: str | None = None) -> Order:
    """Turn the user's cart into an order inside one database transaction.

    Prices, totals and stock are all (re)computed here from the database - the
    client sends nothing but the request itself. Either every step succeeds and
    is committed together, or nothing is changed.
    """
    try:
        order = _build_order(db, user, order_number=order_number)
        db.commit()

    except Exception:
        db.rollback()
        raise
    db.refresh(order)
    logger.info("Order created: id=%s user_id=%s total=%s lines=%s", order.id, user.id, order.total_price, len(order.items))
    return order


def generate_order_number(db: Session) -> str:
    from datetime import UTC, datetime
    import secrets

    while True:
        date_str = datetime.now(UTC).strftime("%Y%m%d")
        rand_suffix = secrets.token_hex(4).upper()
        candidate = f"ORD-{date_str}-{rand_suffix}"
        if db.scalar(select(Order.id).where(Order.order_number == candidate)) is None:
            return candidate


def _build_order(db: Session, user: User, order_number: str | None = None) -> Order:
    from app.services.pc_builder_service import CORE_BUILD_CATEGORIES, normalize_category_slug

    # 1. Lock the cart first: a double-clicked "Checkout" serializes here and the
    #    second request finds an empty cart instead of creating a duplicate order.
    cart = db.scalars(select(Cart).where(Cart.user_id == user.id).with_for_update()).one_or_none()
    cart_items = (
        list(db.scalars(select(CartItem).where(CartItem.cart_id == cart.id).order_by(CartItem.id))) if cart else []
    )
    if not cart_items:
        raise BadRequestError("Your cart is empty")

    # 2. Lock the products so nobody else can sell the same stock meanwhile.
    products = _lock_products(db, (item.product_id for item in cart_items))

    # 3. Validate every line against the *current* product data and build the order.
    order = Order(
        user_id=user.id,
        order_number=order_number or generate_order_number(db),
        status=OrderStatus.PENDING,
        total_price=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
    )

    total = Decimal("0.00")
    for cart_item in cart_items:
        product = products[cart_item.product_id]
        if not product.is_active:
            raise ConflictError(f"'{product.name}' is no longer available")
        if cart_item.quantity > product.stock:
            raise ConflictError(
                f"Insufficient stock for '{product.name}': requested {cart_item.quantity}, available {product.stock}"
            )

        subtotal = product.price * cart_item.quantity
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,  # snapshot: later edits never change past orders
                unit_price=product.price,  # snapshot
                quantity=cart_item.quantity,
                subtotal=subtotal,
            )
        )
        product.stock -= cart_item.quantity
        total += subtotal

    # 5% Build Your Own PC discount if all 8 core categories are present
    categories_present = {
        normalize_category_slug(products[item.product_id].category.slug)
        for item in cart_items
        if products[item.product_id].category is not None
    }
    discount = Decimal("0.00")
    if CORE_BUILD_CATEGORIES.issubset(categories_present):
        build_subtotal = Decimal("0.00")
        for cart_item in cart_items:
            prod = products[cart_item.product_id]
            if prod.category and normalize_category_slug(prod.category.slug) in CORE_BUILD_CATEGORIES:
                build_subtotal += prod.price * cart_item.quantity
        discount = (build_subtotal * Decimal("0.05")).quantize(Decimal("0.01"))

    order.discount_amount = discount
    order.total_price = max(Decimal("0.00"), total - discount)

    # 4. Persist the order and empty the cart (committed by the caller).
    db.add(order)
    db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    db.flush()
    return order


def _list_orders(
    db: Session, conditions: list[ColumnElement[bool]], page: int, limit: int
) -> tuple[list[Order], int]:
    total = db.scalar(select(func.count()).select_from(Order).where(*conditions)) or 0
    stmt = (
        select(Order)
        .where(*conditions)
        .options(selectinload(Order.items), joinedload(Order.user))
        .order_by(Order.created_at.desc(), Order.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return list(db.scalars(stmt)), total


def list_user_orders(db: Session, user: User, *, page: int, limit: int) -> tuple[list[Order], int]:
    return _list_orders(db, [Order.user_id == user.id], page, limit)


def list_all_orders(
    db: Session,
    *,
    status: OrderStatus | None = None,
    search: str | None = None,
    page: int,
    limit: int,
) -> tuple[list[Order], int]:
    conditions: list[ColumnElement[bool]] = []
    if status is not None:
        conditions.append(Order.status == status)
    if search and search.strip():
        escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions.append(
            or_(
                Order.order_number.ilike(pattern, escape="\\"),
                Order.user.has(User.email.ilike(pattern, escape="\\")),
                Order.user.has(User.username.ilike(pattern, escape="\\")),
                Order.user.has(User.first_name.ilike(pattern, escape="\\")),
                Order.user.has(User.last_name.ilike(pattern, escape="\\")),
            )
        )
    return _list_orders(db, conditions, page, limit)


def get_user_order(db: Session, user: User, order_id: int) -> Order:
    # Unknown ids and other people's orders both give 404, so ids cannot be probed.
    order = db.scalars(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user.id)
        .options(selectinload(Order.items), joinedload(Order.user))
    ).one_or_none()
    if order is None:
        raise NotFoundError("Order not found")
    return order


def update_order_status(
    db: Session, order_id: int, new_status: OrderStatus, admin_user_id: int | None = None
) -> Order:
    """Change an order's status (admin). Cancelling returns the stock."""
    try:
        order, old_status = _apply_status(db, order_id, new_status)
        if admin_user_id is not None:
            audit_service.record_audit_log(
                db,
                admin_user_id=admin_user_id,
                action="ORDER_STATUS_CHANGED",
                entity_type="order",
                entity_id=order.id,
                old_value={"status": old_status.value},
                new_value={"status": new_status.value},
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(order)
    return order


def validate_order_transition(current: OrderStatus, new_status: OrderStatus) -> None:
    allowed = ALLOWED_ORDER_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise ConflictError(f"Invalid order status transition: {current.value} -> {new_status.value}")


def _apply_status(db: Session, order_id: int, new_status: OrderStatus) -> tuple[Order, OrderStatus]:
    order = db.scalars(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update(of=Order)  # lock only the order row, never the joined user row
        .options(selectinload(Order.items), joinedload(Order.user))
        .execution_options(populate_existing=True)
    ).one_or_none()
    if order is None:
        raise NotFoundError("Order not found")

    current = order.status
    validate_order_transition(current, new_status)

    if new_status == OrderStatus.CANCELLED:
        _restock(db, order)
    order.status = new_status
    logger.info("Order status changed: id=%s %s -> %s", order.id, current, new_status)
    return order, current


def _restock(db: Session, order: Order) -> None:
    """Give the reserved stock of a cancelled order back to its products."""
    quantities: dict[int, int] = {}
    for item in order.items:
        if item.product_id is not None:  # the product may have been deleted since
            quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
    for product_id, product in _lock_products(db, quantities).items():
        product.stock += quantities[product_id]
