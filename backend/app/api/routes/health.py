import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
def health() -> dict[str, str]:
    """The API process is up and serving requests."""
    return {"status": "ok"}


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    summary="Readiness check (database)",
    responses={503: {"model": DatabaseHealthResponse, "description": "The database is unreachable"}},
)
def health_db(db: DbSession) -> dict[str, str] | JSONResponse:
    """The API can reach PostgreSQL."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "unreachable"})
    return {"status": "ok", "database": "ok"}
