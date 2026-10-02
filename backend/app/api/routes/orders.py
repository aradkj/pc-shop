from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.api.responses import AUTH_RESPONSES, CONFLICT, NOT_FOUND
from app.schemas.common import ErrorResponse, Page, build_page
from app.schemas.order import OrderRead
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"], responses=AUTH_RESPONSES)


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Place an order from my cart",
    description=(
        "Creates an order from the current cart in a single transaction. The request has **no body**: "
        "the server reads prices and quantities from the database, checks that every product is active and "
        "in stock, computes the total, decreases the stock and empties the cart."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "The cart is empty"},
        **CONFLICT,
    },
)
def create_order(user: CurrentUser, db: DbSession):
    return order_service.create_order(db, user)


@router.get("", response_model=Page[OrderRead], summary="List my orders (newest first)")
def list_my_orders(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
):
    items, total = order_service.list_user_orders(db, user, page=page, limit=limit)
    return build_page(items, total, page, limit)


@router.get("/{order_id}", response_model=OrderRead, summary="Get one of my orders", responses=NOT_FOUND)
def get_my_order(order_id: int, user: CurrentUser, db: DbSession):
    return order_service.get_user_order(db, user, order_id)
