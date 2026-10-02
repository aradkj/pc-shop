from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import DbSession, require_admin
from app.api.responses import ADMIN_RESPONSES, CONFLICT, NOT_FOUND
from app.schemas.common import Page, build_page
from app.schemas.product import ProductCreate, ProductFilters, ProductRead, ProductUpdate
from app.services import product_service

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=Page[ProductRead], summary="List products")
def list_products(filters: Annotated[ProductFilters, Query()], db: DbSession):
    """Public catalogue: only active products, with search, filters, sorting and pagination.

    Example: `GET /api/v1/products?search=RTX&category=graphics-cards&max_price=700&page=1&limit=12`
    """
    items, total = product_service.list_products(db, filters)
    return build_page(items, total, filters.page, filters.limit)


@router.get("/{product_id}", response_model=ProductRead, summary="Get a product", responses=NOT_FOUND)
def get_product(product_id: int, db: DbSession):
    return product_service.get_product(db, product_id)


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product (admin)",
    dependencies=[Depends(require_admin)],
    responses={**ADMIN_RESPONSES, **CONFLICT},
)
def create_product(data: ProductCreate, db: DbSession):
    return product_service.create_product(db, data)


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    summary="Update a product (admin)",
    description="Partial update. Set `is_active` to false to hide a product without deleting it.",
    dependencies=[Depends(require_admin)],
    responses={**ADMIN_RESPONSES, **NOT_FOUND, **CONFLICT},
)
def update_product(product_id: int, data: ProductUpdate, db: DbSession):
    return product_service.update_product(db, product_id, data)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product (admin)",
    description="Permanent. Existing orders keep their lines (name and price are snapshots).",
    dependencies=[Depends(require_admin)],
    responses={**ADMIN_RESPONSES, **NOT_FOUND},
)
def delete_product(product_id: int, db: DbSession) -> Response:
    product_service.delete_product(db, product_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
