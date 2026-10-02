from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminUser, DbSession, require_admin
from app.api.responses import ADMIN_RESPONSES, CONFLICT, NOT_FOUND
from app.models.order import OrderStatus
from app.schemas.admin import AdminStats, UserActiveUpdate
from app.schemas.common import Page, build_page
from app.schemas.order import AdminOrderRead, OrderStatusUpdate
from app.schemas.product import ProductFilters, ProductRead
from app.schemas.user import UserRead
from app.services import admin_service, order_service, product_service

# `require_admin` protects every route of this router.
router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
    responses=ADMIN_RESPONSES,
)


@router.get("/stats", response_model=AdminStats, summary="Dashboard counters")
def get_stats(db: DbSession):
    return admin_service.get_stats(db)


@router.get("/products", response_model=Page[ProductRead], summary="List all products, including inactive ones")
def list_all_products(filters: Annotated[ProductFilters, Query()], db: DbSession):
    items, total = product_service.list_products(db, filters, include_inactive=True)
    return build_page(items, total, filters.page, filters.limit)


@router.get("/orders", response_model=Page[AdminOrderRead], summary="List all orders (newest first)")
def list_all_orders(
    db: DbSession,
    status: Annotated[OrderStatus | None, Query(description="Only orders with this status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    items, total = order_service.list_all_orders(db, status=status, page=page, limit=limit)
    return build_page(items, total, page, limit)


@router.patch(
    "/orders/{order_id}/status",
    response_model=AdminOrderRead,
    summary="Change an order's status",
    description=(
        "Any status can be set, except that a cancelled order is final and a completed order cannot be "
        "cancelled. Cancelling an order returns its items to stock."
    ),
    responses={**NOT_FOUND, **CONFLICT},
)
def update_order_status(order_id: int, data: OrderStatusUpdate, db: DbSession):
    return order_service.update_order_status(db, order_id, data.status)


@router.get("/users", response_model=Page[UserRead], summary="List users")
def list_users(
    db: DbSession,
    search: Annotated[str | None, Query(max_length=100, description="Match email, username or name")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    items, total = admin_service.list_users(db, search=search, page=page, limit=limit)
    return build_page(items, total, page, limit)


@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Enable or disable a user account",
    responses=NOT_FOUND,
)
def update_user(user_id: int, data: UserActiveUpdate, admin: AdminUser, db: DbSession):
    return admin_service.set_user_active(db, admin, user_id, data.is_active)
