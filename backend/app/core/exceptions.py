"""Domain errors and the handlers that turn every failure into a JSON response.

Services raise `AppError` subclasses and know nothing about HTTP. Every error
leaves the API in the same shape: `{"detail": "<message>"}`, except validation
errors (422) where `detail` is a list of `{loc, msg, type}` objects.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for errors that should be reported to the client."""

    status_code = 500
    default_detail = "Internal server error"

    def __init__(self, detail: str | None = None, headers: dict[str, str] | None = None) -> None:
        self.detail = detail or self.default_detail
        self.headers = headers
        super().__init__(self.detail)


class BadRequestError(AppError):
    status_code = 400
    default_detail = "Bad request"


class UnauthorizedError(AppError):
    status_code = 401
    default_detail = "Could not validate credentials"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail, headers={"WWW-Authenticate": "Bearer"})


class ForbiddenError(AppError):
    status_code = 403
    default_detail = "You do not have permission to perform this action"


class NotFoundError(AppError):
    status_code = 404
    default_detail = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    default_detail = "Conflict with the current state of the resource"


class TooManyRequestsError(AppError):
    status_code = 429
    default_detail = "Too many requests. Please try again later."

    def __init__(self, detail: str | None = None, retry_after: int = 60) -> None:
        super().__init__(detail, headers={"Retry-After": str(retry_after)})
        self.retry_after = retry_after


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Deliberately drop `input` and `ctx`: they can echo back sensitive values
    # such as a submitted password.
    # Messages from our own validators arrive as "Value error, <text>": show just <text>.
    errors = [
        {"loc": list(err["loc"]), "msg": err["msg"].removeprefix("Value error, "), "type": err["type"]}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Full traceback goes to the logs only - never to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
