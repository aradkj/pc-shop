import logging

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.category import Category
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductFilters, ProductSort, ProductUpdate
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


def get_product(db: Session, product_id: int, *, include_inactive: bool = False) -> Product:
    stmt = select(Product).where(Product.id == product_id).options(joinedload(Product.category))
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


def create_product(db: Session, data: ProductCreate) -> Product:
    _ensure_category_exists(db, data.category_id)
    if data.slug:
        _ensure_slug_available(db, data.slug)
        slug = data.slug
    else:
        slug = unique_slug(db, Product, slugify(data.name))

    product = Product(**data.model_dump(exclude={"slug"}), slug=slug)
    db.add(product)
    _commit(db)
    db.refresh(product)
    logger.info("Product created: id=%s slug=%s", product.id, product.slug)
    return product


def update_product(db: Session, product_id: int, data: ProductUpdate) -> Product:
    product = get_product(db, product_id, include_inactive=True)
    changes = data.model_dump(exclude_unset=True)

    if "category_id" in changes:
        _ensure_category_exists(db, changes["category_id"])
    if "slug" in changes:
        _ensure_slug_available(db, changes["slug"], exclude_id=product.id)

    for field, value in changes.items():
        setattr(product, field, value)
    _commit(db)
    db.refresh(product)
    logger.info("Product updated: id=%s fields=%s", product.id, sorted(changes))
    return product


def delete_product(db: Session, product_id: int) -> None:
    """Permanently delete a product.

    Past orders keep their lines (name and price are snapshots) and carts drop
    the product, both handled by the foreign keys. To merely hide a product from
    the shop, set `is_active` to false instead.
    """
    product = get_product(db, product_id, include_inactive=True)
    db.delete(product)
    db.commit()
    logger.info("Product deleted: id=%s", product_id)
