import json
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.types import Message

from app.core.logging_config import request_id_var
from app.presentation.api import middleware


async def test_rejection_sends_complete_asgi_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(middleware, "RATE_LIMIT_MAX_REQUESTS", 0)
    downstream = AsyncMock()
    send = AsyncMock()
    await middleware.RateLimitMiddleware(downstream)(
        {"type": "http", "client": ("test", 123)}, AsyncMock(), send
    )
    messages: list[Message] = [call.args[0] for call in send.await_args_list]
    assert [m["type"] for m in messages] == ["http.response.start", "http.response.body"]
    assert messages[0]["status"] == 429
    assert "body" not in messages[0]
    assert json.loads(messages[1]["body"])["status"] == 429
    assert not messages[1].get("more_body", False)
    downstream.assert_not_awaited()


async def test_rejection_preserves_cors_timing_and_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings
    from app.main import app

    monkeypatch.setattr(middleware, "RATE_LIMIT_MAX_REQUESTS", 0)
    previous = request_id_var.get()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health", headers={"Origin": settings.cors_origins[0]})
    assert response.status_code == 429
    assert response.json()["trace_id"] == response.headers["x-request-id"]
    assert "x-response-time-ms" in response.headers
    assert "access-control-allow-origin" in response.headers
    assert int(response.headers["content-length"]) == len(response.content)
    assert request_id_var.get() == previous
