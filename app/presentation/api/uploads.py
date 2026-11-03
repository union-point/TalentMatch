from fastapi import HTTPException, UploadFile
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings

UPLOAD_PATHS = {
    "/api/v1/job-descriptions/upload",
    "/api/v1/resumes/upload",
    "/api/v1/resumes/batch-upload",
}
MULTIPART_OVERHEAD_BYTES = 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024


class UploadLimitMiddleware:
    """Bound incoming multipart bodies before the framework spools uploaded files."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "").rstrip("/")
        if scope["type"] != "http" or scope.get("method") != "POST" or path not in UPLOAD_PATHS:
            await self.app(scope, receive, send)
            return

        payload_limit = (
            settings.max_upload_batch_bytes
            if path.endswith("batch-upload")
            else settings.max_upload_file_bytes
        )
        limit = payload_limit + MULTIPART_OVERHEAD_BYTES
        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    length = int(value)
                except ValueError:
                    length = -1
                if length < 0 or length > limit:
                    response = JSONResponse(
                        {"detail": "Invalid request size" if length < 0 else "Upload too large"},
                        status_code=400 if length < 0 else 413,
                    )
                    await response(scope, receive, send)
                    return

        received = 0
        exceeded = False

        async def bounded_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    # Starlette closes partial upload files for MultiPartException.
                    raise MultiPartException("Upload too large")
            return message

        async def send_response(message: Message) -> None:
            if exceeded and message["type"] == "http.response.start":
                # Multipart errors normally become 400; this one is a size violation.
                message = {**message, "status": 413}
            await send(message)

        await self.app(scope, bounded_receive, send_response)


async def read_upload(file: UploadFile, remaining_bytes: int | None = None) -> bytes:
    limit = settings.max_upload_file_bytes
    if remaining_bytes is not None:
        limit = min(limit, remaining_bytes)
    content = bytearray()
    while chunk := await file.read(min(READ_CHUNK_BYTES, limit - len(content) + 1)):
        content.extend(chunk)
        if len(content) > limit:
            raise HTTPException(status_code=413, detail="Upload too large")
    return bytes(content)
