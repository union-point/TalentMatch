"""Assign the locked legacy workspace through a normal email/MFA invitation."""

import argparse
import asyncio

from email_validator import EmailNotValidError, validate_email

from app.application.services.auth_sessions import AuthError
from app.infrastructure.persistence.database import engine
from app.infrastructure.security.auth_services import get_auth_services


async def invite(email: str) -> None:
    services = get_auth_services()
    try:
        await services.organizations.invite_legacy_owner(email)
    finally:
        await services.throttle.redis.aclose()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--email", required=True, help="New or unassigned owner's verified email inbox"
    )
    args = parser.parse_args()
    try:
        email = validate_email(args.email, check_deliverability=False).normalized.lower()
        asyncio.run(invite(email))
    except (EmailNotValidError, AuthError) as exc:
        parser.exit(1, f"{exc}\n")
    print("Legacy owner invitation queued. The recipient must verify email and complete MFA setup.")


if __name__ == "__main__":
    main()
