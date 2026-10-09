from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession
from app.api.responses import AUTH_RESPONSES, CONFLICT, NOT_FOUND
from app.schemas.cart import CartRead
from app.schemas.common import ErrorResponse
from app.schemas.pc_builder import (
    AddBuildToCartRequest,
    BuilderOptionsResponse,
    BuildValidationRequest,
    BuildValidationResponse,
    GPURecommendation,
)
from app.services import pc_builder_service

router = APIRouter(prefix="/pc-builder", tags=["PC Builder"])


@router.get(
    "/options",
    response_model=BuilderOptionsResponse,
    summary="Get available PC builder component options",
    description="Returns active catalog products grouped by component category for PC building.",
)
def get_builder_options(
    db: DbSession,
    category: Annotated[str | None, Query(description="Filter by category slug")] = None,
):
    return pc_builder_service.get_builder_options(db, category_slug=category)


@router.get(
    "/recommendations/gpu",
    response_model=list[GPURecommendation],
    summary="Get GPU recommendations for a selected CPU",
    description="Ranks and scores available GPUs based on compatibility and performance pairing with the CPU.",
    responses=NOT_FOUND,
)
def get_gpu_recommendations(
    db: DbSession,
    cpu_id: Annotated[int, Query(ge=1, description="Product ID of the selected CPU")],
):
    return pc_builder_service.get_gpu_recommendations(db, cpu_id=cpu_id)


@router.post(
    "/validate",
    response_model=BuildValidationResponse,
    summary="Validate PC component compatibility and pricing",
    description=(
        "Performs authoritative backend rule-based checks on selected components: "
        "socket matching, memory compatibility, PSU wattage, form factor clearances, "
        "and calculates exact subtotal and 5% Build Your Own PC discount if complete."
    ),
)
def validate_build(data: BuildValidationRequest, db: DbSession):
    return pc_builder_service.validate_build(
        db, components_map=data.components, product_ids=data.product_ids
    )


@router.post(
    "/price",
    response_model=BuildValidationResponse,
    summary="Calculate authoritative build price and discount",
    description="Computes exact subtotal, 5% complete-build discount, and final total using backend PostgreSQL prices.",
)
def calculate_build_price(data: BuildValidationRequest, db: DbSession):
    return pc_builder_service.validate_build(
        db, components_map=data.components, product_ids=data.product_ids
    )


@router.post(
    "/add-to-cart",
    response_model=CartRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add validated PC build components to shopping cart",
    description="Validates the build and adds all selected components into the customer's cart under transaction lock.",
    responses={
        **AUTH_RESPONSES,
        400: {"model": ErrorResponse, "description": "Incompatible or invalid build"},
        **CONFLICT,
    },
)
def add_build_to_cart(data: AddBuildToCartRequest, user: CurrentUser, db: DbSession):
    return pc_builder_service.add_build_to_cart(
        db,
        user=user,
        components_map=data.components,
        product_ids=data.product_ids,
        clear_existing=data.clear_existing,
    )
