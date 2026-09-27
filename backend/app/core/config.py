"""
Application configuration.

Phase 1 scope only: app metadata, environment name, and CORS configuration.
Database, Redis, and AI provider settings are added in later phases
(Phase 2, Phase 3, Phase 4 respectively) and must not be anticipated here.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, sourced from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application metadata -------------------------------------------------
    APP_NAME: str = "CivicPulse API"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True

    # --- CORS -------------------------------------------------------------
    # Comma-separated list of allowed origins, e.g.
    #   CORS_ORIGINS=http://localhost:5173,http://localhost:3000
    # Kept explicit (no wildcard) so that credentials-bearing requests from the
    # frontend are only ever accepted from known origins.
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Allow CORS_ORIGINS to be supplied as a comma-separated env string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    # --- API ----------------------------------------------------------------
    API_V1_PREFIX: str = "/api"


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings accessor.

    Using a cached factory (rather than a module-level singleton) makes it
    straightforward to override settings in tests via dependency overrides
    or by clearing the cache (`get_settings.cache_clear()`).
    """
    return Settings()
