import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AIResponseError,
    AnalysisNotFoundError,
    FileNotFoundError,
    InjectionDetectedError,
    JobDescriptionNotFoundError,
    ParsingError,
    ResumeNotFoundError,
    UnsupportedFileTypeError,
    public_error_message,
)
from app.core.logging_config import request_id_var

logger = logging.getLogger(__name__)

HTTP_STATUS_MAP: dict[type[Exception], int] = {
    UnsupportedFileTypeError: 400,
    ParsingError: 422,
    InjectionDetectedError: 422,
    FileNotFoundError: 404,
    AIResponseError: 502,
    ResumeNotFoundError: 404,
    JobDescriptionNotFoundError: 404,
    AnalysisNotFoundError: 404,
}


def _make_problem_response(
    status: int,
    title: str,
    detail: str,
    request_id: str | None,
    extra: dict[str, object] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"https://httpstatuses.org/{status}",
        "title": title,
        "status": status,
        "detail": detail,
    }
    if request_id:
        body["trace_id"] = request_id
    if extra:
        body["extra"] = extra
    return JSONResponse(
        status_code=status,
        content=body,
        headers={"X-Request-ID": request_id} if request_id else None,
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or request_id_var.get()

    status = HTTP_STATUS_MAP.get(type(exc), 500)
    title = "InternalServerError" if status == 500 else exc.__class__.__name__
    detail = public_error_message(exc)

    extra: dict[str, object] | None = None
    if isinstance(exc, InjectionDetectedError):
        extra = exc.details
    elif isinstance(exc, UnsupportedFileTypeError):
        extra = {"file_type": exc.file_type}

    if status == 500:
        logger.error("Unhandled exception (trace=%s)", request_id, exc_info=exc)
    else:
        logger.warning(
            "Request error (trace=%s): %s - %s",
            request_id,
            title,
            detail,
        )

    return _make_problem_response(status, title, detail, request_id, extra)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or request_id_var.get()
    extra: dict[str, object] | None = None
    if isinstance(exc, RequestValidationError):
        extra = {
            "errors": [
                {"field": ".".join(str(part) for part in error["loc"]), "type": error["type"]}
                for error in exc.errors()
            ]
        }
    logger.warning("Request validation failed (trace=%s)", request_id)
    return _make_problem_response(
        422, "ValidationError", "Request validation failed.", request_id, extra
    )
