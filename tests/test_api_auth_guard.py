"""Tests for API Authentication Guard & Unauthenticated Access Enforcement (Issue #028 / DoD-SEC1)."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.application.practice_service import PracticeService
from src.application.rag_service import RAGService
from src.infrastructure.auth_provider import GoogleAuthProvider
from src.infrastructure.config import Settings
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.infrastructure.llm_provider import GoogleGenAIProvider
from src.infrastructure.qdrant_store import QdrantVectorStore
from src.infrastructure.question_repository import LocalQuestionRepository
from src.presentation.api.deps import (
    get_auth_provider,
    get_history_repository,
    get_llm_provider,
    get_practice_service,
    get_question_repository,
    get_rag_service,
    get_settings,
    get_vector_store,
)
from src.presentation.api.main import create_app


@pytest.fixture
def auth_guard_env(tmp_path: Path) -> Generator[dict, None, None]:
    """Provide hermetic test environment for auth guard testing."""
    test_db_path = tmp_path / "test_auth_guard.db"
    test_repo = SQLitePracticeHistoryRepository(db_path=test_db_path)
    test_question_repo = LocalQuestionRepository()

    mock_vector_store = MagicMock(spec=QdrantVectorStore)
    mock_vector_store.count.return_value = 25
    mock_vector_store.search_hybrid.return_value = []

    test_llm_provider = GoogleGenAIProvider(api_key="AIzaSyTestMockKey123456789")
    test_llm_provider.generate_answer = MagicMock(return_value="Mocked AI response")  # type: ignore[method-assign]

    test_auth_provider = GoogleAuthProvider(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret-salt",
        redirect_uri="http://localhost:8000/api/auth/callback",
        allowed_emails=["allowed@example.com"],
    )

    test_settings_enabled = Settings(
        gemini_api_key="AIzaSyTestMockKey123456789",
        auth_enabled=True,
        allowed_emails=["allowed@example.com"],
        google_client_id="test-client-id.apps.googleusercontent.com",
        google_client_secret="test-client-secret-salt",
        google_redirect_uri="http://localhost:8000/api/auth/callback",
        sqlite_db_path=str(test_db_path),
        session_secret="test-session-secret-for-auth-guard-testing",
    )

    test_settings_disabled = Settings(
        gemini_api_key="AIzaSyTestMockKey123456789",
        auth_enabled=False,
        sqlite_db_path=str(test_db_path),
    )

    yield {
        "repo": test_repo,
        "question_repo": test_question_repo,
        "vector_store": mock_vector_store,
        "llm_provider": test_llm_provider,
        "auth_provider": test_auth_provider,
        "settings_enabled": test_settings_enabled,
        "settings_disabled": test_settings_disabled,
    }


def _create_test_client(
    env: dict, auth_enabled: bool = True
) -> tuple[TestClient, GoogleAuthProvider]:
    """Helper to instantiate TestClient with hermetic dependency overrides."""
    app = create_app()
    active_settings = env["settings_enabled"] if auth_enabled else env["settings_disabled"]
    auth_provider = env["auth_provider"]

    app.dependency_overrides[get_settings] = lambda: active_settings
    app.dependency_overrides[get_auth_provider] = lambda: auth_provider
    app.dependency_overrides[get_history_repository] = lambda: env["repo"]
    app.dependency_overrides[get_question_repository] = lambda: env["question_repo"]
    app.dependency_overrides[get_vector_store] = lambda: env["vector_store"]
    app.dependency_overrides[get_llm_provider] = lambda: env["llm_provider"]
    app.dependency_overrides[get_practice_service] = lambda: PracticeService(
        question_repo=env["question_repo"], history_repo=env["repo"]
    )
    app.dependency_overrides[get_rag_service] = lambda: RAGService(
        vector_store=env["vector_store"],
        llm_provider=env["llm_provider"],
        question_repo=env["question_repo"],
    )

    client = TestClient(app, raise_server_exceptions=False)
    return client, auth_provider


class TestApiAuthGuard:
    """Acceptance criteria tests for API authentication guard (Scenario 5, 6, 7)."""

    def test_unauthenticated_request_rejected_with_401(self, auth_guard_env: dict):
        """Scenario 5: When auth_enabled=True and no session cookie is provided, protected APIs return 401."""
        client, _ = _create_test_client(auth_guard_env, auth_enabled=True)

        protected_endpoints = [
            ("GET", "/api/practice/sessions/active"),
            ("GET", "/api/questions"),
            ("GET", "/api/analytics/summary"),
            ("GET", "/api/system/settings"),
            ("POST", "/api/rag/explain", {"question_id": "dummy-q", "user_choice": "ア"}),
        ]

        for method, url, *body in protected_endpoints:
            if method == "GET":
                resp = client.get(url)
            else:
                resp = client.post(url, json=body[0] if body else {})
            assert resp.status_code == 401, (
                f"Expected 401 for {method} {url}, got {resp.status_code}: {resp.text}"
            )
            assert "認証が必要です" in resp.json()["detail"] or "Unauthorized" in resp.text

    def test_invalid_token_request_rejected_with_401(self, auth_guard_env: dict):
        """Scenario 5: When session token is tampered or invalid, return 401 Unauthorized."""
        client, _ = _create_test_client(auth_guard_env, auth_enabled=True)
        client.cookies.set("session_user", "tampered.invalid.token")

        resp = client.get("/api/practice/sessions/active")
        assert resp.status_code == 401
        assert "無効または期限切れのセッションです" in resp.json()["detail"]

    def test_expired_token_request_rejected_with_401(self, auth_guard_env: dict):
        """Scenario: When session token has expired (now > expires_at), return 401 Unauthorized."""
        client, auth_provider = _create_test_client(auth_guard_env, auth_enabled=True)
        expired_token = auth_provider.generate_session_token("allowed@example.com", max_age_days=-1)
        client.cookies.set("session_user", expired_token)

        resp = client.get("/api/practice/sessions/active")
        assert resp.status_code == 401
        assert "無効または期限切れのセッションです" in resp.json()["detail"]

    def test_unauthorized_email_rejected_with_403(self, auth_guard_env: dict):
        """Scenario 6: When session token is valid but email is not in allowed_emails whitelist, return 403 Forbidden."""
        client, auth_provider = _create_test_client(auth_guard_env, auth_enabled=True)
        unauthorized_token = auth_provider.generate_session_token("unauthorized_user@example.com")
        client.cookies.set("session_user", unauthorized_token)

        resp = client.get("/api/practice/sessions/active")
        assert resp.status_code == 403
        assert "アクセスが許可されていません" in resp.json()["detail"]

    def test_authorized_user_allowed_with_200(self, auth_guard_env: dict):
        """Scenario 5 / 6: When session token is valid and email is allowed, access succeeds."""
        client, auth_provider = _create_test_client(auth_guard_env, auth_enabled=True)
        valid_token = auth_provider.generate_session_token("allowed@example.com")
        client.cookies.set("session_user", valid_token)

        resp = client.get("/api/practice/sessions/active")
        assert resp.status_code == 200

        resp_q = client.get("/api/questions?limit=5")
        assert resp_q.status_code == 200

        resp_s = client.get("/api/system/settings")
        assert resp_s.status_code == 200

    def test_auth_disabled_bypass_with_200(self, auth_guard_env: dict):
        """Scenario 4: When auth_enabled=False (local development), requests without cookie succeed."""
        client, _ = _create_test_client(auth_guard_env, auth_enabled=False)

        resp = client.get("/api/practice/sessions/active")
        assert resp.status_code == 200

        resp_q = client.get("/api/questions?limit=5")
        assert resp_q.status_code == 200

    def test_public_endpoints_accessible_without_auth(self, auth_guard_env: dict):
        """Scenario 7: Public endpoints (/health, /api/auth/*) remain accessible without authentication when auth is enabled."""
        client, _ = _create_test_client(auth_guard_env, auth_enabled=True)

        # Health endpoints
        resp_h1 = client.get("/health")
        assert resp_h1.status_code == 200
        assert resp_h1.json()["status"] == "healthy"

        resp_h2 = client.get("/api/health")
        assert resp_h2.status_code == 200

        # Auth endpoints
        resp_status = client.get("/api/auth/status")
        assert resp_status.status_code == 200
        assert resp_status.json()["auth_enabled"] is True
        assert resp_status.json()["authenticated"] is False

        resp_login = client.get("/api/auth/login")
        assert resp_login.status_code == 200
        assert "accounts.google.com" in resp_login.json()["login_url"]


def test_settings_session_secret_key_alias() -> None:
    """Settings should accept both session_secret and session_secret_key aliases."""
    from src.infrastructure.config import Settings

    # Accepts session_secret_key alias
    s1 = Settings(auth_enabled=True, session_secret_key="my-secret-key-1234")  # type: ignore[call-arg]
    assert s1.session_secret == "my-secret-key-1234"

    # Accepts session_secret directly
    s2 = Settings(auth_enabled=True, session_secret="my-secret-key-5678")
    assert s2.session_secret == "my-secret-key-5678"

