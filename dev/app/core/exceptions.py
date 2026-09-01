import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings

logger = logging.getLogger("app")


class AppError(Exception):
    status_code = 500

    def __init__(self, message: str, *, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class DocumentNotFoundError(AppError):
    status_code = 404


class ConnectorError(AppError):
    status_code = 502


class ActionNotFoundError(AppError):
    status_code = 404


async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("%s: %s", exc.__class__.__name__, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.__class__.__name__, "message": exc.message, "details": exc.details},
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    settings = get_settings()
    message = str(exc) if settings.debug else "An unexpected error occurred."
    return JSONResponse(
        status_code=500,
        content={"error": "InternalServerError", "message": message},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
