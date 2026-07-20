import time
import uuid
from collections.abc import Callable

from starlette.types import ASGIApp

from app.core.logging_config import request_id_var

RATE_LIMIT_WINDOW = 60.0
RATE_LIMIT_MAX_REQUESTS = 100
_request_history: dict[str, list[float]] = {}


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)

        async def send_with_id(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"X-Request-ID", request_id.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_id)


class TimingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()

        async def send_with_timing(message: dict) -> None:
            if message["type"] == "http.response.start":
                elapsed = time.monotonic() - start
                headers = list(message.get("headers", []))
                headers.append((
                    b"X-Response-Time-Ms",
                    str(round(elapsed * 1000)).encode(),
                ))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_timing)


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client_ip = scope.get("client", ("unknown",))[0]
        now = time.monotonic()
        window_start = now - RATE_LIMIT_WINDOW

        history = _request_history.setdefault(client_ip, [])
        history[:] = [t for t in history if t > window_start]

        if len(history) >= RATE_LIMIT_MAX_REQUESTS:
            from app.presentation.api.errors import _make_problem_response

            resp = _make_problem_response(
                429,
                "RateLimitExceeded",
                f"Too many requests. Limit: {RATE_LIMIT_MAX_REQUESTS} per "
                f"{RATE_LIMIT_WINDOW:.0f}s",
                request_id_var.get(),
            )

            async def send_429(message: dict) -> None:
                if message["type"] == "http.response.start":
                    message["status"] = resp.status_code
                    headers = list(message.get("headers", []))
                    for k, v in resp.headers.items():
                        if k.lower() not in ("content-length", "content-type"):
                            headers.append((
                                k.lower().encode(),
                                v.encode() if isinstance(v, str) else v,
                            ))
                    headers.append((b"content-type", b"application/json"))
                    message["headers"] = headers
                    message["body"] = resp.body
                await send(message)

            await send_429({
                "type": "http.response.start",
                "status": 429,
                "headers": [],
            })
            return

        history.append(now)
        await self.app(scope, receive, send)
