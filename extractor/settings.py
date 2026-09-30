"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings; values come from .env or the process environment."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_api_key: str
    llm_api_base: str = "https://opencode.ai/zen/v1"
    llm_model: str = "space-bunny-free"
    upload_dir: str = "uploads"
    match_threshold: int = Field(default=85, ge=0, le=100)
    max_file_size_mb: int = Field(default=10, ge=1, le=100)

    @property
    def max_file_size_bytes(self) -> int:
        """Per-file upload cap in bytes."""
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings, with a readable message on bad config."""
    try:
        return Settings()
    except ValidationError as exc:
        raise RuntimeError(
            "invalid or missing configuration; copy .env.example to .env and "
            f"fill in the required values. Details: {exc}"
        ) from exc
