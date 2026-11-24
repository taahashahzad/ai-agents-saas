"""Application errors and the handlers that give every error one JSON shape:

    {"error": {"code": "...", "message": "...", "details": [...]?}}
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    message: str = "Internal server error."

    def __init__(self, message: str | None = None, *, code: str | None = None,
                 headers: dict[str, str] | None = None):
        super().__init__(message or self.message)
        if message:
            self.message = message
        if code:
            self.code = code
        self.headers = headers


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_required"
    message = "Authentication required."

    def __init__(self, message: str | None = None, *, code: str | None = None):
        super().__init__(message, code=code, headers={"WWW-Authenticate": "Bearer"})


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "Bad request."


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"
    message = "The file is too large."


class UnsupportedMediaTypeError(AppError):
    status_code = 415
    code = "unsupported_file_type"
    message = "Unsupported file type."


class UnprocessableFileError(AppError):
    status_code = 422
    code = "invalid_file"
    message = "The file is invalid or corrupted."


class UnprocessableEntityError(AppError):
    status_code = 422
    code = "unprocessable"
    message = "The request could not be processed."


class BadGatewayError(AppError):
    status_code = 502
    code = "storage_error"
    message = "File storage is temporarily unavailable. Please try again."


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "Service temporarily unavailable."


def _body(code: str, message: str, details: list | None = None) -> dict:
    error: dict = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message),
                            headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        # Deliberately omit the submitted input so request data is never echoed or logged.
        details = [
            {"loc": [str(p) for p in e.get("loc", [])], "msg": e.get("msg"), "type": e.get("type")}
            for e in exc.errors()
        ]
        return JSONResponse(status_code=422,
                            content=_body("validation_error", "Request validation failed.", details))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code,
                            content=_body(f"http_{exc.status_code}", str(exc.detail)),
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Log the exception type and route only: no headers, tokens or bodies.
        logger.error("Unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
        return JSONResponse(status_code=500, content=_body("internal_error", "Internal server error."))
