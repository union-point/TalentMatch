from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.application.dto.auth import VerificationResult

Password = Annotated[str, Field(min_length=15, max_length=128)]


class AuthBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailBody(AuthBody):
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalized_email(cls, value: str) -> str:
        return value.strip().lower()


class RegisterBody(EmailBody):
    password: Password
    organization_name: Annotated[str, Field(min_length=1, max_length=255)]

    @field_validator("organization_name")
    @classmethod
    def organization_name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Organization name is required")
        return value.strip()


class LoginBody(EmailBody):
    password: Annotated[str, Field(min_length=1, max_length=128)]


class TokenBody(AuthBody):
    token: Annotated[str, Field(min_length=20, max_length=128)]


class VerifyEmailResponse(BaseModel):
    status: VerificationResult
    detail: str = "Email verified. Sign in to continue."


class ResetBody(TokenBody):
    password: Password


class ChangePasswordBody(AuthBody):
    password: Annotated[str, Field(min_length=1, max_length=128)]
    new_password: Password


class FactorBody(AuthBody):
    code: Annotated[str, Field(min_length=6, max_length=128)]


class EnrollmentBody(AuthBody):
    password: Annotated[str, Field(min_length=1, max_length=128)]
    code: Annotated[str | None, Field(max_length=128)] = None


class ManageMfaBody(FactorBody):
    password: Annotated[str, Field(min_length=1, max_length=128)]


class AcceptInvitationBody(TokenBody):
    password: Password | None = None
