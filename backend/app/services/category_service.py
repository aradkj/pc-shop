import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.category import Category
from app.models.product import Product
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.slugs import slugify, unique_slug

logger = logging.getLogger(__name__)


def list_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name)))


def get_category(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Category not found")
    return category


def _ensure_name_available(db: Session, name: str, *, exclude_id: int | None = None) -> None:
    stmt = select(Category.id).where(func.lower(Category.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Category.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError("A category with this name already exists")


def _ensure_slug_available(db: Session, slug: str, *, exclude_id: int | None = None) -> None:
    stmt = select(Category.id).where(Category.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(Category.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError("A category with this slug already exists")


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:  # concurrent request won the race for the same name/slug
        db.rollback()
        raise ConflictError("A category with this name or slug already exists") from None


def create_category(db: Session, data: CategoryCreate) -> Category:
    _ensure_name_available(db, data.name)
    if data.slug:
        _ensure_slug_available(db, data.slug)
        slug = data.slug
    else:
        slug = unique_slug(db, Category, slugify(data.name))

    category = Category(name=data.name, slug=slug, description=data.description)
    db.add(category)
    _commit(db)
    db.refresh(category)
    logger.info("Category created: id=%s slug=%s", category.id, category.slug)
    return category


def update_category(db: Session, category_id: int, data: CategoryUpdate) -> Category:
    category = get_category(db, category_id)
    changes = data.model_dump(exclude_unset=True)

    if "name" in changes:
        _ensure_name_available(db, changes["name"], exclude_id=category.id)
    if "slug" in changes:
        _ensure_slug_available(db, changes["slug"], exclude_id=category.id)

    for field, value in changes.items():
        setattr(category, field, value)
    _commit(db)
    db.refresh(category)
    logger.info("Category updated: id=%s", category.id)
    return category


def delete_category(db: Session, category_id: int) -> None:
    category = get_category(db, category_id)
    product_count = db.scalar(select(func.count()).select_from(Product).where(Product.category_id == category.id))
    if product_count:
        raise ConflictError(f"Cannot delete a category that still has {product_count} product(s)")

    db.delete(category)
    try:
        db.commit()
    except IntegrityError:  # a product was added after the check above (ON DELETE RESTRICT)
        db.rollback()
        raise ConflictError("Cannot delete a category that still has products") from None
    logger.info("Category deleted: id=%s", category_id)
