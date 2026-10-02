"""FastAPI application entry point: `uvicorn app.main:app`."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.api.routes import health
from app.core.config import API_V1_PREFIX, get_settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging

logger = logging.getLogger(__name__)

DESCRIPTION = """
REST API of **Arad Store**, an online shop for PC components and gaming gear.

* Authenticate with `POST /api/v1/auth/login`, then send `Authorization: Bearer <token>`
  (or use the **Authorize** button above).
* Public: product and category browsing. Customers: cart, orders, profile. Admins: catalogue
  management, all orders, users.
"""

TAGS_METADATA = [
    {"name": "Auth", "description": "Registration, login (JWT) and the current user."},
    {"name": "Products", "description": "Public catalogue. Create / update / delete are admin-only."},
    {"name": "Categories", "description": "Product categories. Create / update / delete are admin-only."},
    {"name": "Cart", "description": "The authenticated user's shopping cart."},
    {"name": "Orders", "description": "Checkout and order history of the authenticated user."},
    {"name": "Admin", "description": "Admin-only: dashboard stats, all orders, users."},
    {"name": "Health", "description": "Liveness and readiness probes."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("Starting Arad Store API %s (env=%s)", __version__, settings.app_env)
    if settings.has_placeholder_secret:
        logger.warning("SECRET_KEY is a placeholder - generate a real secret before deploying")
    yield
    engine.dispose()
    logger.info("Arad Store API stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Arad Store API",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        lifespan=lifespan,
    )
    # Tokens travel in the Authorization header (no cookies), so credentials are not allowed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router, prefix=API_V1_PREFIX)
    return app


app = create_app()
