from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.application.dto.auth import AuthContext
from app.application.services.auth_service import GENERIC_EMAIL_MESSAGE
from app.application.services.auth_sessions import principal
from app.infrastructure.security.auth_services import AuthServices, get_auth_services
from app.presentation.api.auth_dependencies import get_auth_context
from app.presentation.api.routes.auth import reserve
from app.presentation.schemas.auth import EmailBody

router = APIRouter(prefix="/api/v1/organization", tags=["organization"])


@router.get("")
async def organization(context: AuthContext = Depends(get_auth_context)) -> dict[str, str]:
    actor = principal(context)
    assert context.organization is not None
    return {"id": str(actor.organization_id), "name": context.organization.name, "role": actor.role}


@router.get("/members")
async def members(
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> list[dict[str, str]]:
    return [
        {"id": str(user.id), "email": user.email, "role": membership.role}
        for user, membership in await services.organizations.list_members(context)
    ]


@router.get("/invitations")
async def invitations(
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> list[dict[str, str]]:
    return [
        {"id": str(token.id), "email": token.email, "expires_at": token.expires_at.isoformat()}
        for token in await services.organizations.list_invitations(context)
    ]


@router.post("/invitations", status_code=202)
async def invite(
    body: EmailBody,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> dict[str, str]:
    principal(context, owner=True)
    await reserve(services, request, str(body.email), email=True)
    await services.organizations.invite(context, str(body.email))
    return {"detail": GENERIC_EMAIL_MESSAGE}


@router.delete("/invitations/{token_id}", status_code=204)
async def revoke(
    token_id: UUID,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> None:
    await services.organizations.revoke_invitation(context, token_id)


@router.delete("/members/{user_id}", status_code=204)
async def remove(
    user_id: UUID,
    context: AuthContext = Depends(get_auth_context),
    services: AuthServices = Depends(get_auth_services),
) -> None:
    await services.organizations.remove_member(context, user_id)
