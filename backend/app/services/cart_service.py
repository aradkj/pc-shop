import logging

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.user import User
from app.schemas.cart import MAX_ITEM_QUANTITY

logger = logging.getLogger(__name__)


def _get_cart_row(db: Session, user_id: int, *, lock: bool = False) -> Cart:
    """Return the user's cart, creating it on first use.

    With `lock=True` the row is locked (`SELECT ... FOR UPDATE`) until the
    transaction ends, which serializes concurrent changes to the same cart.
    """
    stmt = select(Cart).where(Cart.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    cart = db.scalars(stmt).one_or_none()
    if cart is not None:
        return cart

    db.add(Cart(user_id=user_id))
    try:
        db.commit()
    except IntegrityError:  # another request created the cart first
        db.rollback()
    return _get_cart_row(db, user_id, lock=lock)


def get_cart(db: Session, user: User) -> Cart:
    """Return the cart with its items and their products loaded."""
    cart = _get_cart_row(db, user.id)
    stmt = (
        select(Cart)
        .where(Cart.id == cart.id)
        .options(selectinload(Cart.items).joinedload(CartItem.product))
        .execution_options(populate_existing=True)
    )
    return db.scalars(stmt).one()


def _ensure_purchasable(product: Product, quantity: int) -> None:
    if not product.is_active:
        raise ConflictError(f"'{product.name}' is no longer available")
    if quantity > product.stock:
        raise ConflictError(f"Only {product.stock} unit(s) of '{product.name}' in stock")
    if quantity > MAX_ITEM_QUANTITY:
        raise BadRequestError(f"You can buy at most {MAX_ITEM_QUANTITY} units of a product at once")


def _find_item(db: Session, cart: Cart, item_id: int) -> CartItem:
    # Filtering by cart_id is what stops a user from touching someone else's cart item.
    item = db.scalars(
        select(CartItem)
        .where(CartItem.id == item_id, CartItem.cart_id == cart.id)
        .options(selectinload(CartItem.product))
        .with_for_update()
    ).one_or_none()
    if item is None:
        raise NotFoundError("Cart item not found")
    return item



def add_item(db: Session, user: User, product_id: int, quantity: int) -> CartItem:
    """Add a product to the cart safely under transactional lock."""
    cart = _get_cart_row(db, user.id, lock=True)

    # Lock product row in consistent order (Cart -> Product)
    product = db.scalars(
        select(Product)
        .where(Product.id == product_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if product is None or not product.is_active:
        raise NotFoundError("Product not found")

    item = db.scalar(
        select(CartItem)
        .where(CartItem.cart_id == cart.id, CartItem.product_id == product.id)
        .with_for_update()
    )

    new_quantity = (item.quantity if item else 0) + quantity
    _ensure_purchasable(product, new_quantity)

    if item is None:
        item = CartItem(cart_id=cart.id, product_id=product.id, quantity=new_quantity)
        db.add(item)
    else:
        item.quantity = new_quantity
    cart.updated_at = func.now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Could not add item to cart due to concurrent conflict") from None

    db.refresh(item)
    return item


def update_item(db: Session, user: User, item_id: int, quantity: int) -> CartItem:
    """Update item quantity in cart safely with lock on both cart and product."""
    cart = _get_cart_row(db, user.id, lock=True)
    item = _find_item(db, cart, item_id)

    # Lock the product to ensure stock and active status are fresh
    product = db.scalars(
        select(Product)
        .where(Product.id == item.product_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one_or_none()
    if product is None or not product.is_active:
        raise ConflictError(f"'{item.product.name}' is no longer available")
    _ensure_purchasable(product, quantity)

    item.quantity = quantity
    cart.updated_at = func.now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Could not update item due to concurrent conflict") from None

    db.refresh(item)
    return item


def remove_item(db: Session, user: User, item_id: int) -> None:
    cart = _get_cart_row(db, user.id, lock=True)
    item = _find_item(db, cart, item_id)
    db.delete(item)
    cart.updated_at = func.now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Could not remove item due to concurrent conflict") from None


def clear_cart(db: Session, user: User) -> None:
    cart = _get_cart_row(db, user.id, lock=True)
    db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    cart.updated_at = func.now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Could not clear cart due to concurrent conflict") from None
