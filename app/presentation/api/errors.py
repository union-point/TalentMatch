import logging

from fastapi import Request
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
    return JSONResponse(status_code=status, content=body)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request_id_var.get()

    status = HTTP_STATUS_MAP.get(type(exc), 500)
    title = exc.__class__.__name__
    detail = str(exc)

    extra: dict[str, object] | None = None
    if isinstance(exc, InjectionDetectedError):
        extra = exc.details
    elif isinstance(exc, AIResponseError):
        if exc.raw_response is not None:
            extra = {"raw_response_preview": str(exc.raw_response)[:500]}
    elif isinstance(exc, UnsupportedFileTypeError):
        extra = {"file_type": exc.file_type}

    if status == 500:
        logger.exception("Unhandled exception: %s", exc)
    else:
        logger.warning(
            "Request error (trace=%s): %s - %s",
            request_id,
            title,
            detail,
        )

    return _make_problem_response(status, title, detail, request_id, extra)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request_id_var.get()
    detail = str(exc)
    logger.warning("Validation error (trace=%s): %s", request_id, detail)
    return _make_problem_response(422, "ValidationError", detail, request_id)
