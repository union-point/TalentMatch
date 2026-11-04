import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging_config import request_id_var

RATE_LIMIT_WINDOW = 60.0
RATE_LIMIT_MAX_REQUESTS = 100
_request_history: dict[str, list[float]] = {}


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers = [(key, value) for key, value in headers if key.lower() != b"x-request-id"]
                headers.append((b"X-Request-ID", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


class TimingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()

        async def send_with_timing(message: Message) -> None:
            if message["type"] == "http.response.start":
                elapsed = time.monotonic() - start
                headers = list(message.get("headers", []))
                headers.append(
                    (
                        b"X-Response-Time-Ms",
                        str(round(elapsed * 1000)).encode(),
                    )
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_timing)


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
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
                f"Too many requests. Limit: {RATE_LIMIT_MAX_REQUESTS} per {RATE_LIMIT_WINDOW:.0f}s",
                request_id_var.get(),
            )

            await resp(scope, receive, send)
            return

        history.append(now)
        await self.app(scope, receive, send)


class PrivateResponseMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def private_send(message: Message) -> None:
            if message["type"] == "http.response.start" and scope.get("path", "").startswith(
                "/api/"
            ):
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in {b"cache-control", b"referrer-policy"}
                ]
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"referrer-policy", b"no-referrer"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, private_send)
