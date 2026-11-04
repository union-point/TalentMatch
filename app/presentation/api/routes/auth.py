from fastapi import APIRouter, Depends, Request, Response

from app.application.dto.auth import AuthContext
from app.application.services.auth_service import GENERIC_EMAIL_MESSAGE
from app.config import settings
from app.infrastructure.security.auth_services import AuthServices, get_auth_services
from app.presentation.api.auth_dependencies import get_auth_context, set_auth_cookie
from app.presentation.schemas.auth import (
    AcceptInvitationBody,
    ChangePasswordBody,
    EmailBody,
    EnrollmentBody,
    FactorBody,
    LoginBody,
    ManageMfaBody,
    RegisterBody,
    ResetBody,
    TokenBody,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def session_view(context: AuthContext) -> dict[str, object]:
    return {
        "state": context.session.state,
        "csrf_token": context.session.csrf_token,
        "user": {
            "id": str(context.user.id),
            "email": context.user.email,
            "verified": context.user.verified_at is not None,
        }
        if context.user
        else None,
        "organization": {
            "id": str(context.organization.id),
            "name": context.organization.name,
            "role": context.membership.role,
            "locked": context.organization.locked,
        }
        if context.organization and context.membership
        else None,
        "mfa_enabled": context.mfa_enabled,
    }


async def reserve(
    services: AuthServices, request: Request, account: str, email: bool = False
) -> tuple[str, str]:
    return await services.throttle.reserve(
        "email" if email else "login",
        account,
        request.client.host if request.client else "unknown",
        settings.auth_email_account_limit if email else settings.auth_login_account_limit,
        settings.auth_email_ip_limit if email else settings.auth_login_ip_limit,
        3600 if email else 300,
    )


@router.get("/session")
async def session(
    request: Request, response: Response, services: AuthServices = Depends(get_auth_services)
) -> dict[str, object]:
    ip = request.client.host if request.client else "unknown"
    await services.throttle.reserve("bootstrap", ip, ip, 60, 60, 60)
    context = await services.sessions.resolve(
        request.cookies.get(settings.auth_cookie_name), bootstrap=True
    )
    set_auth_cookie(response, context)
    return session_view(context)


@router.post("/register", status_code=202)
async def register(
    body: RegisterBody,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, str]:
    await reserve(services, request, str(body.email), email=True)
    await services.auth.register(str(body.email), body.password, body.organization_name)
    return {"detail": GENERIC_EMAIL_MESSAGE}


@router.post("/login")
async def login(
    body: LoginBody,
    request: Request,
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, object]:
    keys = await reserve(services, request, str(body.email))
    context = await services.auth.login(str(body.email), body.password, context)
    await services.throttle.release(keys)
    set_auth_cookie(response, context)
    return session_view(context)


@router.post("/verify-email")
async def verify_email(
    body: TokenBody,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, str]:
    keys = await reserve(services, request, "verify:" + body.token)
    await services.auth.verify_email(body.token)
    await services.throttle.release(keys)
    return {"detail": "Email verified. Sign in to continue."}


@router.post("/resend-verification", status_code=202)
async def resend(
    body: EmailBody,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, str]:
    await reserve(services, request, str(body.email), email=True)
    await services.auth.request_email(str(body.email), "verify")
    return {"detail": GENERIC_EMAIL_MESSAGE}


@router.post("/forgot-password", status_code=202)
async def forgot(
    body: EmailBody,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, str]:
    await reserve(services, request, str(body.email), email=True)
    await services.auth.request_email(str(body.email), "reset")
    return {"detail": GENERIC_EMAIL_MESSAGE}


@router.post("/reset-password")
async def reset(
    body: ResetBody,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, str]:
    keys = await reserve(services, request, "reset:" + body.token)
    await services.auth.reset_password(body.token, body.password)
    await services.throttle.release(keys)
    return {"detail": "Password reset. Sign in to continue."}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordBody,
    request: Request,
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, object]:
    keys = await reserve(services, request, str(context.session.user_id) + ":password")
    context = await services.auth.change_password(context, body.password, body.new_password)
    await services.throttle.release(keys)
    set_auth_cookie(response, context)
    return session_view(context)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> None:
    await services.sessions.logout(context)
    response.delete_cookie(
        settings.auth_cookie_name,
        path="/",
        secure=not settings.auth_allow_insecure_cookies,
        httponly=True,
        samesite="lax",
    )


@router.post("/logout-all", status_code=204)
async def logout_all(
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> None:
    await services.sessions.logout(context, all_sessions=True)
    response.delete_cookie(
        settings.auth_cookie_name,
        path="/",
        secure=not settings.auth_allow_insecure_cookies,
        httponly=True,
        samesite="lax",
    )


@router.post("/mfa/challenge")
async def challenge(
    body: FactorBody,
    request: Request,
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, object]:
    keys = await reserve(services, request, str(context.session.user_id) + ":mfa")
    context = await services.mfa.challenge(context, body.code)
    await services.throttle.release(keys)
    set_auth_cookie(response, context)
    return session_view(context)


@router.post("/mfa/enroll")
async def enroll(
    body: EnrollmentBody,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, str]:
    keys = await reserve(services, request, str(context.session.user_id) + ":mfa")
    uri, qr = await services.mfa.begin(context, body.password, body.code)
    await services.throttle.release(keys)
    return {"uri": uri, "qr_code": qr}


@router.post("/mfa/confirm")
async def confirm(
    body: FactorBody,
    request: Request,
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, object]:
    keys = await reserve(services, request, str(context.session.user_id) + ":mfa")
    context, codes = await services.mfa.confirm(context, body.code)
    await services.throttle.release(keys)
    set_auth_cookie(response, context)
    return {**session_view(context), "recovery_codes": codes}


@router.post("/mfa/recovery-codes")
async def recovery_codes(
    body: ManageMfaBody,
    request: Request,
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, object]:
    keys = await reserve(services, request, str(context.session.user_id) + ":mfa")
    context, codes = await services.mfa.manage(context, body.password, body.code)
    await services.throttle.release(keys)
    set_auth_cookie(response, context)
    return {**session_view(context), "recovery_codes": codes}


@router.post("/mfa/disable")
async def disable_mfa(
    body: ManageMfaBody,
    request: Request,
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, object]:
    keys = await reserve(services, request, str(context.session.user_id) + ":mfa")
    context, _ = await services.mfa.manage(context, body.password, body.code, disable=True)
    await services.throttle.release(keys)
    set_auth_cookie(response, context)
    return session_view(context)


@router.post("/accept-invitation")
async def accept(
    body: AcceptInvitationBody,
    request: Request,
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, object]:
    keys = await reserve(services, request, "invite:" + body.token[:16])
    context = await services.organizations.accept(context, body.token, body.password)
    await services.throttle.release(keys)
    set_auth_cookie(response, context)
    return session_view(context)
