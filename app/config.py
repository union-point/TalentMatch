from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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
    ai_deep_analysis_provider: str = "gemini"
    ai_deep_analysis_model: str = "gemini-3.1-flash-lite"
    deep_analysis_timeout_seconds: int = Field(default=240, gt=0)

    # OpenAI-compatible provider settings (optional)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"


settings = Settings()
