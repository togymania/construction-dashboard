"""Application configuration using pydantic-settings.

Environment variables are loaded from the .env file in development. In
production (Render / Railway / Fly), they come straight from the
platform's environment.

The DATABASE_URL is handled specially: hosted Postgres providers
(Neon, Supabase, Render's own) hand you a ``postgresql://...`` URL.
SQLAlchemy needs ``postgresql+asyncpg://...``. We accept either form and
normalise.
"""
from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The built-in development secret. It is committed and therefore public,
# so it must never be used to sign tokens in production.
_DEV_SECRET_KEY = "dev_secret_key_change_in_production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # ---- Application ----
    PROJECT_NAME: str = "Construction Management API"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Comma-separated list of allowed origins for CORS. In dev we accept
    # localhost; in production this gets set to the Vercel URL.
    CORS_ORIGINS: str = "http://localhost:3000"

    # ---- Security ----
    SECRET_KEY: str = _DEV_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # ---- Database ----
    # Pieces (used only if DATABASE_URL is not supplied directly).
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "construction_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    # Full URL override. When a managed Postgres (Neon, Supabase, etc.) is
    # used the platform hands us a single connection string. We accept
    # either ``postgresql://...`` or ``postgresql+asyncpg://...`` and
    # normalise inside the DATABASE_URL property below.
    DATABASE_URL_OVERRIDE: str = ""

    # ---- File uploads ----
    # In production we mount a persistent disk at /app/uploads (when
    # available) so PDFs survive restarts. In dev we just use ./uploads
    # in the backend folder.
    UPLOADS_DIR: str = "uploads"

    # ---- Limits ----
    MAX_IMPORT_FILE_SIZE_MB: int = 5
    MAX_LEDGER_IMPORT_MB: int = 25  # HIPODROM workbook is ~11MB
    MAX_PDF_SIZE_MB: int = 100

    # ---- LLM ----
    # Leave ANTHROPIC_API_KEY empty to use rule-based fallback. When set,
    # contract parsing, profile reports, daily briefings and executive
    # reports flip to real Claude calls.
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    LLM_TIMEOUT_SECONDS: int = 120

    # -------------------------------------------------------------------
    # Computed URLs
    # -------------------------------------------------------------------

    @property
    def DATABASE_URL(self) -> str:
        """Async PostgreSQL connection string for SQLAlchemy.

        If DATABASE_URL_OVERRIDE is set, we use it (normalising
        ``postgresql://`` to ``postgresql+asyncpg://`` and stripping any
        ``?sslmode=require`` query that asyncpg can't read).
        """
        if self.DATABASE_URL_OVERRIDE:
            return _to_async_url(self.DATABASE_URL_OVERRIDE)
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Sync PostgreSQL connection string for Alembic migrations."""
        if self.DATABASE_URL_OVERRIDE:
            return _to_sync_url(self.DATABASE_URL_OVERRIDE)
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def CORS_ORIGINS_LIST(self) -> list[str]:
        """Parse CORS_ORIGINS env into a clean list."""
        return [
            o.strip()
            for o in (self.CORS_ORIGINS or "").split(",")
            if o.strip()
        ]

    # -------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------

    @model_validator(mode="after")
    def _enforce_production_secret(self) -> "Settings":
        """Refuse to boot in production with the built-in dev SECRET_KEY.

        The default key is committed and public; signing JWTs with it in
        production would let anyone forge access tokens. Set SECRET_KEY via
        the platform environment (Render / Railway / Fly) instead.
        """
        if (
            self.ENVIRONMENT.strip().lower() == "production"
            and self.SECRET_KEY == _DEV_SECRET_KEY
        ):
            raise ValueError(
                "SECRET_KEY must be set via the environment in production; "
                "the default development key is not allowed."
            )
        return self


def _to_async_url(url: str) -> str:
    """Normalize a Postgres URL to asyncpg form."""
    cleaned = _strip_sslmode(url)
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql://" + cleaned[len("postgres://"):]
    if cleaned.startswith("postgresql://"):
        cleaned = "postgresql+asyncpg://" + cleaned[len("postgresql://"):]
    return cleaned


def _to_sync_url(url: str) -> str:
    """Normalize a Postgres URL to the synchronous (psycopg2) form Alembic uses."""
    cleaned = _strip_sslmode(url)
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql://" + cleaned[len("postgres://"):]
    if cleaned.startswith("postgresql+asyncpg://"):
        cleaned = "postgresql://" + cleaned[len("postgresql+asyncpg://"):]
    return cleaned


def _strip_sslmode(url: str) -> str:
    """asyncpg rejects ``?sslmode=require``; it negotiates SSL on its own."""
    if "?" not in url:
        return url
    base, _, query = url.partition("?")
    keep_parts = []
    for part in query.split("&"):
        if not part:
            continue
        key, _, _value = part.partition("=")
        if key.lower() in {"sslmode", "channel_binding"}:
            continue
        keep_parts.append(part)
    return base + ("?" + "&".join(keep_parts) if keep_parts else "")


settings = Settings()
