from typing import Self
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", hide_input_in_errors=True
    )

    database_url: str
    gemini_api_key: str
    redis_url: str
    cors_origins: list[str]
    upload_dir: str = "./uploads"
    log_level: str = "INFO"
    max_upload_file_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_upload_batch_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    max_upload_files: int = Field(default=20, gt=0)
    max_document_pages: int = Field(default=50, gt=0)
    document_timeout_seconds: int = Field(default=120, gt=0)

    ai_fast_track_provider: str = "gemini"
    ai_fast_track_model: str = "gemini-3.1-flash-lite"
    ai_deep_analysis_provider: str = "openai"
    ai_deep_analysis_model: str = "gemini-3.1-flash-lite"
    deep_analysis_dispatch_batch_size: int = Field(default=100, gt=0)
    deep_analysis_dispatch_retry_seconds: int = Field(default=900, gt=0)
    deep_analysis_timeout_seconds: int = Field(default=240, gt=0)

    environment: str = "production"
    public_origin: str = "https://localhost"
    auth_allow_insecure_cookies: bool = False
    auth_encryption_keys: list[str] = []
    auth_session_idle_seconds: int = Field(default=1800, gt=0)
    auth_session_absolute_seconds: int = Field(default=43200, gt=0)
    auth_challenge_seconds: int = Field(default=600, gt=0)
    auth_verification_seconds: int = Field(default=86400, gt=0)
    auth_reset_seconds: int = Field(default=1800, gt=0)
    auth_invitation_seconds: int = Field(default=259200, gt=0)
    auth_login_account_limit: int = Field(default=5, gt=0)
    auth_login_ip_limit: int = Field(default=30, gt=0)
    auth_email_account_limit: int = Field(default=3, gt=0)
    auth_email_ip_limit: int = Field(default=20, gt=0)
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=587, gt=0, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "TalentMatch <no-reply@localhost>"
    smtp_starttls: bool = True
    smtp_timeout_seconds: int = Field(default=15, gt=0)

    @property
    def auth_cookie_name(self) -> str:
        return "talentmatch_session" if self.auth_allow_insecure_cookies else "__Host-talentmatch"

    @model_validator(mode="after")
    def validate_auth_configuration(self) -> Self:
        origin = urlsplit(self.public_origin)
        if (
            origin.scheme not in {"http", "https"}
            or not origin.netloc
            or origin.path
            or origin.query
            or origin.fragment
            or origin.username
        ):
            raise ValueError("PUBLIC_ORIGIN must be an origin without a path or credentials")
        if self.auth_allow_insecure_cookies and self.environment not in {"development", "test"}:
            raise ValueError("Insecure auth cookies require development or test environment")
        if origin.scheme != "https" and not self.auth_allow_insecure_cookies:
            raise ValueError("Production authentication requires HTTPS")
        for key in self.auth_encryption_keys:
            Fernet(key.encode())
        return self

    # OpenAI-compatible provider settings (optional)
    openai_api_key: str = "api-key"
    openai_base_url: str = "http://host.docker.internal:8080/v1"


settings = Settings()
