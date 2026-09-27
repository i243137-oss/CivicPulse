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

    # --- Database (PostgreSQL / async access) --------------------------------
    # Supports both POSTGRES_HOST (standard Docker compose/K8s) and POSTGRES_SERVER
    POSTGRES_HOST: str | None = None
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "civicpulse"
    DATABASE_URL: str | None = None

    @property
    def postgres_host(self) -> str:
        """Resolved PostgreSQL host address."""
        return self.POSTGRES_HOST or self.POSTGRES_SERVER

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Async database URL for SQLAlchemy async engine."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            if url.startswith("postgres://"):
                return url.replace("postgres://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.postgres_host}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Sync database URL for Alembic migrations and synchronous tooling."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql+asyncpg://"):
                return url.replace("postgresql+asyncpg://", "postgresql://", 1)
            if url.startswith("sqlite+aiosqlite://"):
                return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
            return url
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.postgres_host}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Redis (Cache & Rate Limiting) ---------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0
    REDIS_URL: str | None = None
    REDIS_STATS_CACHE_TTL: int = 30  # 30-second TTL as required by specification

    # --- Distributed Rate Limiting -------------------------------------------
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    @property
    def REDIS_CONNECTION_URL(self) -> str:
        """Construct Redis connection URL."""
        if self.REDIS_URL:
            return self.REDIS_URL
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings accessor.

    Using a cached factory (rather than a module-level singleton) makes it
    straightforward to override settings in tests via dependency overrides
    or by clearing the cache (`get_settings.cache_clear()`).
    """
    return Settings()
