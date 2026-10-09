"""Aggregates every versioned route module under one router."""

from fastapi import APIRouter

from app.api.routes import admin, auth, cart, categories, orders, pc_builder, products

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(categories.router)
api_router.include_router(cart.router)
api_router.include_router(orders.router)
api_router.include_router(admin.router)
api_router.include_router(pc_builder.router)
