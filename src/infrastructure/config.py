"""Application configuration using Pydantic Settings."""

import json
import os
from typing import Any

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for IPA Exam RAG."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Gemini Settings
    gemini_api_key: str = Field(default="", description="Google GenAI API Key")
    gemini_model_generate: str = Field(
        default="gemini-3.7-flash", description="Generation & Reasoning model"
    )
    gemini_model_generate_fallback: str = Field(
        default="gemini-3.5-flash-lite",
        description="Fallback generation model when primary fails or is unavailable",
    )
    gemini_max_retries: int = Field(
        default=3, ge=1, description="Maximum retry attempts for transient Gemini API errors"
    )
    gemini_retry_delay_seconds: float = Field(
        default=1.0, gt=0.0, description="Initial retry delay seconds for exponential backoff"
    )
    gemini_retry_backoff_factor: float = Field(
        default=2.0, ge=1.0, description="Multiplier for retry delay"
    )
    gemini_model_embedding: str = Field(default="gemini-embedding-2", description="Embedding model")
    embedding_dimension: int = Field(default=768, description="MRL dimension (e.g. 768 or 1536)")

    # Qdrant Vector Store Settings
    qdrant_url: str | None = Field(default=None, description="Qdrant Cloud URL")
    qdrant_api_key: str | None = Field(default=None, description="Qdrant API Key")
    qdrant_collection_name: str = Field(
        default="ipa-exam-rag", description="Qdrant collection name"
    )
    qdrant_location: str | None = Field(
        default=None, description="Optional local storage path or ':memory:'"
    )

    # Self-growth thresholds
    judge_confidence_threshold: float = Field(
        default=0.85, description="Minimum confidence score for Judge approval"
    )
    dedup_similarity_threshold: float = Field(
        default=0.88, description="Cosine similarity threshold for duplicate merging"
    )

    # SQLite Practice History Settings
    sqlite_db_path: str = Field(
        default="data/practice_history.db",
        description="Path to SQLite practice history database file or ':memory:'",
    )

    # Google OAuth 2.0 Authentication Settings
    auth_enabled: bool = Field(
        default=True,
        description=(
            "Whether to enforce Google OAuth authentication. Secure by default; "
            "set AUTH_ENABLED=false explicitly for local development only."
        ),
    )
    google_client_id: str = Field(
        default="",
        description="Google OAuth 2.0 Client ID",
    )
    google_client_secret: str = Field(
        default="",
        description="Google OAuth 2.0 Client Secret",
    )
    google_redirect_uri: str = Field(
        default="",
        description="Google OAuth 2.0 Redirect URI (e.g. https://xxx.run.app)",
    )
    allowed_emails: list[str] | str = Field(
        default_factory=list,
        description="List of authorized Google account email addresses",
    )
    session_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("session_secret", "session_secret_key"),
        description="Dedicated secret key for HMAC session and CSRF state signing",
    )
    cookie_secure: bool = Field(
        default=False,
        description="Whether session cookies require HTTPS Secure flag (forced True in HTTPS requests)",
    )

    # CORS Settings
    allowed_cors_origins: list[str] | str = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="Allowed CORS origins for local development and web frontends",
    )

    @field_validator("allowed_cors_origins", mode="before")
    @classmethod
    def parse_allowed_cors_origins(cls, v: Any) -> list[str]:
        """Parse comma-separated string, JSON string, or list of origins."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return []
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(item).strip().rstrip("/") for item in parsed if item]
                except Exception:
                    stripped = stripped[1:-1].strip()
            return [item.strip().rstrip("/") for item in stripped.split(",") if item.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(item).strip().rstrip("/") for item in v if item]
        return []

    @field_validator("allowed_emails", mode="before")
    @classmethod
    def parse_allowed_emails(cls, v: Any) -> list[str]:
        """Parse comma-separated string, JSON string, or list into a list of strings."""
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return []
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [
                            str(item).strip().strip("'\"").lower()
                            for item in parsed
                            if str(item).strip().strip("'\"")
                        ]
                except Exception:
                    stripped = stripped[1:-1].strip()
            return [
                item.strip().strip("'\"").lower()
                for item in stripped.split(",")
                if item.strip().strip("'\"")
            ]
        if isinstance(v, (list, tuple, set)):
            return [
                str(item).strip().strip("'\"").lower()
                for item in v
                if str(item).strip().strip("'\"")
            ]
        return []

    @model_validator(mode="after")
    def require_session_secret_when_auth_enabled(self) -> "Settings":
        """Reject startup if auth is enabled but session_secret is not set.

        session_secret is used for HMAC signing of session tokens and OAuth
        state parameters. Running with auth_enabled=True and no secret renders
        the HMAC signatures invalid, creating a security hole.
        Fail-fast at startup rather than silently accepting the unsafe state.
        """
        if self.auth_enabled and not self.session_secret:
            raise ValueError(
                "AUTH CONFIGURATION ERROR: 'session_secret' must be set when 'auth_enabled' is True. "
                'Generate a strong random secret (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`) '
                "and set SESSION_SECRET in your environment or .env file."
            )
        return self

    @model_validator(mode="after")
    def forbid_auth_disabled_on_cloud_run(self) -> "Settings":
        """Reject startup on Cloud Run when authentication is disabled.

        Cloud Run injects the K_SERVICE environment variable into every container.
        A publicly reachable deployment with auth disabled would expose billable
        Gemini operations (reindex), API key rotation, and history deletion.
        """
        if not self.auth_enabled and os.environ.get("K_SERVICE"):
            raise ValueError(
                "AUTH CONFIGURATION ERROR: 'auth_enabled' must be True on Cloud Run "
                f"(K_SERVICE={os.environ.get('K_SERVICE')!r}). "
                "Remove AUTH_ENABLED=false from the service environment variables."
            )
        return self


settings = Settings()
