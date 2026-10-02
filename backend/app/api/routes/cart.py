from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.api.responses import AUTH_RESPONSES, CONFLICT, NOT_FOUND
from app.schemas.cart import CartItemCreate, CartItemRead, CartItemUpdate, CartRead
from app.services import cart_service

# Every endpoint works on the *authenticated user's* cart - there is no cart id in
# any URL, so one user can never address another user's cart.
router = APIRouter(prefix="/cart", tags=["Cart"], responses=AUTH_RESPONSES)


@router.get("", response_model=CartRead, summary="Get my cart")
def get_cart(user: CurrentUser, db: DbSession):
    return cart_service.get_cart(db, user)


@router.post(
    "/items",
    response_model=CartItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a product to my cart",
    description="If the product is already in the cart its quantity is increased.",
    responses={**NOT_FOUND, **CONFLICT},
)
def add_cart_item(data: CartItemCreate, user: CurrentUser, db: DbSession):
    return cart_service.add_item(db, user, data.product_id, data.quantity)


@router.patch(
    "/items/{item_id}",
    response_model=CartItemRead,
    summary="Set the quantity of a cart item",
    responses={**NOT_FOUND, **CONFLICT},
)
def update_cart_item(item_id: int, data: CartItemUpdate, user: CurrentUser, db: DbSession):
    return cart_service.update_item(db, user, item_id, data.quantity)


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an item from my cart",
    responses=NOT_FOUND,
)
def remove_cart_item(item_id: int, user: CurrentUser, db: DbSession) -> Response:
    cart_service.remove_item(db, user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Empty my cart")
def clear_cart(user: CurrentUser, db: DbSession) -> Response:
    cart_service.clear_cart(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
