"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the FireLens API.

    Values can be provided through environment variables or a local ``.env``
    file. See ``.env.example`` for the supported variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "FireLens API"
    app_version: str = "1.0.0"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # The existing Supabase Session Pooler URL is reused directly. The
    # ``SecretStr`` wrapper prevents credentials from appearing in repr output.
    # SQLAlchemy-style ``postgresql+asyncpg://`` URLs are accepted and normalized
    # by ``database_dsn``.
    database_url: SecretStr = SecretStr("postgresql://localhost:5432/firelens")
    database_pool_min_size: int = Field(default=1, ge=0, le=50)
    database_pool_max_size: int = Field(default=10, ge=1, le=100)
    database_connect_timeout: float = Field(default=15.0, gt=0, le=120)
    database_command_timeout: float = Field(default=30.0, gt=0, le=300)

    # Comma-separated list, e.g. "http://localhost:3000,https://firelens.app".
    # A single "*" allows every origin (useful for local prototypes only).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Optional shared secret. When set, the CSV export requires an
    # ``X-API-Key`` header. ``SecretStr`` keeps it out of settings reprs.
    api_key: SecretStr | None = None

    # NASA FIRMS map key used by data-ingestion jobs (not required by the API
    # itself, but kept here so jobs can share one configuration source).
    firms_map_key: str | None = None

    default_page_size: int = Field(default=100, ge=1, le=1000)
    max_page_size: int = Field(default=1000, ge=1, le=5000)
    max_calendar_days: int = Field(default=366, ge=1, le=3660)
    historical_min_years: int = Field(default=3, ge=1, le=50)
    anomaly_moderate_threshold: float = Field(default=2.5, gt=0)
    anomaly_high_threshold: float = Field(default=3.5, gt=0)
    export_batch_size: int = Field(default=500, ge=1, le=10_000)
    export_chunk_size: int = Field(default=16_384, ge=1024, le=1_048_576)

    @model_validator(mode="after")
    def validate_pool_and_thresholds(self) -> Self:
        if self.database_pool_min_size > self.database_pool_max_size:
            raise ValueError("database_pool_min_size must be <= database_pool_max_size")
        if self.anomaly_moderate_threshold >= self.anomaly_high_threshold:
            raise ValueError(
                "anomaly_moderate_threshold must be less than anomaly_high_threshold"
            )
        return self

    @property
    def database_dsn(self) -> str:
        """Return an asyncpg-compatible DSN without exposing it in repr output."""
        dsn = self.database_url.get_secret_value()
        if dsn.startswith("postgresql+asyncpg://"):
            return "postgresql://" + dsn.removeprefix("postgresql+asyncpg://")
        if dsn.startswith("postgres://"):
            return "postgresql://" + dsn.removeprefix("postgres://")
        return dsn

    @property
    def cors_origin_list(self) -> list[str]:
        """Return CORS origins as a normalized list."""
        origins = [origin.strip() for origin in self.cors_origins.split(",")]
        return [origin for origin in origins if origin]

    @property
    def docs_url(self) -> str:
        return "/docs"

    @property
    def redoc_url(self) -> str:
        return "/redoc"


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
