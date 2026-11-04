from fastapi import Depends, Request, Response

from app.application.dto.auth import AuthContext
from app.application.services.auth_sessions import principal
from app.config import settings
from app.domain.entities.identity import Principal
from app.infrastructure.security.auth_services import AuthServices, get_auth_services


def set_auth_cookie(response: Response, context: AuthContext) -> None:
    if context.cookie_token:
        response.set_cookie(
            settings.auth_cookie_name,
            context.cookie_token,
            httponly=True,
            secure=not settings.auth_allow_insecure_cookies,
            samesite="lax",
            path="/",
            max_age=max(
                1, int((context.session.expires_at - context.session.last_seen_at).total_seconds())
            ),
        )
    response.headers["Cache-Control"] = "no-store"


async def get_auth_context(
    request: Request, services: AuthServices = Depends(get_auth_services)
) -> AuthContext:
    return await services.sessions.resolve(
        request.cookies.get(settings.auth_cookie_name),
        csrf=request.headers.get("X-CSRF-Token"),
        origin=request.headers.get("Origin"),
        unsafe=request.method not in {"GET", "HEAD", "OPTIONS"},
    )


async def get_principal(context: AuthContext = Depends(get_auth_context)) -> Principal:
    return principal(context)
