import logging

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.category import Category
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductFilters, ProductSort, ProductUpdate
from app.services import audit_service
from app.services.slugs import slugify, unique_slug

logger = logging.getLogger(__name__)

MAX_SEARCH_TERMS = 5

_SORT_ORDER = {
    ProductSort.NEWEST: (Product.created_at.desc(), Product.id.desc()),
    ProductSort.PRICE_ASC: (Product.price.asc(), Product.id.asc()),
    ProductSort.PRICE_DESC: (Product.price.desc(), Product.id.asc()),
    ProductSort.NAME: (Product.name.asc(), Product.id.asc()),
}


def _like_pattern(term: str) -> str:
    """Contains-pattern for ILIKE with the user's `%`, `_` and `\\` escaped."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _conditions(filters: ProductFilters, *, include_inactive: bool) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if not include_inactive:
        conditions.append(Product.is_active.is_(True))

    # Every word must match the name, brand or description ("ryzen 7800x3d" finds "Ryzen 7 7800X3D").
    for term in (filters.search or "").split()[:MAX_SEARCH_TERMS]:
        pattern = _like_pattern(term)
        conditions.append(
            or_(
                Product.name.ilike(pattern, escape="\\"),
                Product.brand.ilike(pattern, escape="\\"),
                Product.description.ilike(pattern, escape="\\"),
            )
        )

    if filters.category_id is not None:
        conditions.append(Product.category_id == filters.category_id)
    if filters.category:
        conditions.append(Product.category.has(Category.slug == filters.category.lower()))
    if filters.brand:
        conditions.append(func.lower(Product.brand) == filters.brand.lower())
    if filters.min_price is not None:
        conditions.append(Product.price >= filters.min_price)
    if filters.max_price is not None:
        conditions.append(Product.price <= filters.max_price)
    return conditions


def list_products(
    db: Session, filters: ProductFilters, *, include_inactive: bool = False
) -> tuple[list[Product], int]:
    """Return one page of products and the total number of matches."""
    conditions = _conditions(filters, include_inactive=include_inactive)
    total = db.scalar(select(func.count()).select_from(Product).where(*conditions)) or 0
    stmt = (
        select(Product)
        .where(*conditions)
        .options(joinedload(Product.category))
        .order_by(*_SORT_ORDER[filters.sort])
        .offset((filters.page - 1) * filters.limit)
        .limit(filters.limit)
    )
    return list(db.scalars(stmt)), total


def get_product(db: Session, identifier: int | str, *, include_inactive: bool = False) -> Product:
    stmt = select(Product).options(joinedload(Product.category))
    if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
        stmt = stmt.where(Product.id == int(identifier))
    else:
        stmt = stmt.where(Product.slug == str(identifier))
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    product = db.scalars(stmt).one_or_none()
    if product is None:
        raise NotFoundError("Product not found")
    return product


def _ensure_category_exists(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise BadRequestError("Category does not exist")


def _ensure_slug_available(db: Session, slug: str, *, exclude_id: int | None = None) -> None:
    stmt = select(Product.id).where(Product.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(Product.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError("A product with this slug already exists")


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:  # concurrent request won the race for the same slug
        db.rollback()
        raise ConflictError("A product with this slug already exists") from None


def create_product(db: Session, data: ProductCreate, admin_user_id: int | None = None) -> Product:
    _ensure_category_exists(db, data.category_id)
    if data.slug:
        _ensure_slug_available(db, data.slug)
        slug = data.slug
    else:
        slug = unique_slug(db, Product, slugify(data.name))

    product = Product(**data.model_dump(exclude={"slug"}), slug=slug)
    db.add(product)
    try:
        db.flush()
        if admin_user_id is not None:
            audit_service.record_audit_log(
                db,
                admin_user_id=admin_user_id,
                action="PRODUCT_CREATED",
                entity_type="product",
                entity_id=product.id,
                new_value={"name": product.name, "slug": product.slug, "price": str(product.price)},
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("A product with this slug already exists") from None

    db.refresh(product)

    logger.info("Product created: id=%s slug=%s", product.id, product.slug)
    return product


def update_product(
    db: Session, product_id: int, data: ProductUpdate, admin_user_id: int | None = None
) -> Product:
    product = get_product(db, product_id, include_inactive=True)
    changes = data.model_dump(exclude_unset=True)

    if "category_id" in changes:
        _ensure_category_exists(db, changes["category_id"])
    if "slug" in changes:
        _ensure_slug_available(db, changes["slug"], exclude_id=product.id)

    old_values = {}
    for field, value in changes.items():
        old_val = getattr(product, field)
        old_values[field] = str(old_val) if hasattr(old_val, "isoformat") or hasattr(old_val, "as_tuple") else old_val
        setattr(product, field, value)

    if admin_user_id is not None:
        audit_service.record_audit_log(
            db,
            admin_user_id=admin_user_id,
            action="PRODUCT_UPDATED",
            entity_type="product",
            entity_id=product.id,
            old_value=old_values,
            new_value={k: str(v) if hasattr(v, "isoformat") or hasattr(v, "as_tuple") else v for k, v in changes.items()},
        )

    _commit(db)
    db.refresh(product)

    logger.info("Product updated: id=%s fields=%s", product.id, sorted(changes))
    return product


def delete_product(db: Session, product_id: int, admin_user_id: int | None = None) -> None:
    """Permanently delete a product.

    Past orders keep their lines (name and price are snapshots) and carts drop
    the product, both handled by the foreign keys. To merely hide a product from
    the shop, set `is_active` to false instead.
    """
    product = get_product(db, product_id, include_inactive=True)
    old_info = {"name": product.name, "slug": product.slug}
    db.delete(product)

    if admin_user_id is not None:
        audit_service.record_audit_log(
            db,
            admin_user_id=admin_user_id,
            action="PRODUCT_DELETED",
            entity_type="product",
            entity_id=product_id,
            old_value=old_info,
        )

    db.commit()

    logger.info("Product deleted: id=%s", product_id)
