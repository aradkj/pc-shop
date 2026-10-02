from fastapi import APIRouter, Depends, Response, status

from app.api.deps import DbSession, require_admin
from app.api.responses import ADMIN_RESPONSES, CONFLICT, NOT_FOUND
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryRead], summary="List categories")
def list_categories(db: DbSession):
    return category_service.list_categories(db)


@router.get("/{category_id}", response_model=CategoryRead, summary="Get a category", responses=NOT_FOUND)
def get_category(category_id: int, db: DbSession):
    return category_service.get_category(db, category_id)


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category (admin)",
    dependencies=[Depends(require_admin)],
    responses={**ADMIN_RESPONSES, **CONFLICT},
)
def create_category(data: CategoryCreate, db: DbSession):
    return category_service.create_category(db, data)


@router.patch(
    "/{category_id}",
    response_model=CategoryRead,
    summary="Update a category (admin)",
    dependencies=[Depends(require_admin)],
    responses={**ADMIN_RESPONSES, **NOT_FOUND, **CONFLICT},
)
def update_category(category_id: int, data: CategoryUpdate, db: DbSession):
    return category_service.update_category(db, category_id, data)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category (admin)",
    description="A category that still contains products cannot be deleted (409).",
    dependencies=[Depends(require_admin)],
    responses={**ADMIN_RESPONSES, **NOT_FOUND, **CONFLICT},
)
def delete_category(category_id: int, db: DbSession) -> Response:
    category_service.delete_category(db, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
