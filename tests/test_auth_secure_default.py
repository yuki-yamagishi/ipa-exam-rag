"""Secure-by-default authentication configuration tests (ISSUE-001)."""

import pytest
from pydantic import ValidationError

from src.infrastructure.config import Settings


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove auth-related env vars so that code defaults are exercised."""
    for key in ("AUTH_ENABLED", "K_SERVICE", "SESSION_SECRET", "SESSION_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_auth_enabled_by_default(clean_env: pytest.MonkeyPatch) -> None:
    """Scenario 1: With no AUTH_ENABLED set, authentication is enabled."""
    s = Settings(_env_file=None, session_secret="x" * 32)  # type: ignore[call-arg]
    assert s.auth_enabled is True


def test_default_without_session_secret_fails_fast(clean_env: pytest.MonkeyPatch) -> None:
    """Scenario 2: Default (auth on) without SESSION_SECRET refuses to start."""
    with pytest.raises(ValidationError, match="session_secret"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_local_development_can_disable_auth(clean_env: pytest.MonkeyPatch) -> None:
    """Scenario 3: Outside Cloud Run, AUTH_ENABLED=false is allowed explicitly."""
    clean_env.setenv("AUTH_ENABLED", "false")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.auth_enabled is False


def test_cloud_run_rejects_auth_disabled(clean_env: pytest.MonkeyPatch) -> None:
    """Scenario 4: On Cloud Run (K_SERVICE set), AUTH_ENABLED=false refuses to start."""
    clean_env.setenv("K_SERVICE", "ipa-exam-rag")
    clean_env.setenv("AUTH_ENABLED", "false")
    with pytest.raises(ValidationError, match="must be True on Cloud Run"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_cloud_run_with_auth_enabled_starts(clean_env: pytest.MonkeyPatch) -> None:
    """Scenario 5: On Cloud Run with auth enabled and secret set, startup succeeds."""
    clean_env.setenv("K_SERVICE", "ipa-exam-rag")
    s = Settings(_env_file=None, session_secret="x" * 32)  # type: ignore[call-arg]
    assert s.auth_enabled is True
