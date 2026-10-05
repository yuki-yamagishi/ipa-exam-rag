"""Tests for System Settings & Google OAuth Authentication API (Issue #018 / DoD-B7)."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.application.practice_service import PracticeService
from src.application.rag_service import RAGService
from src.domain.models import AnswerKey, DojoMode, DojoSessionState
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
    get_question_repository,
    get_rag_service,
    get_settings,
    get_vector_store,
)
from src.presentation.api.main import create_app


@pytest.fixture
def system_and_auth_env(tmp_path: Path) -> Generator[dict, None, None]:
    """Provide fully hermetic test environment for system and auth APIs."""
    test_db_path = tmp_path / "test_system_auth.db"
    test_repo = SQLitePracticeHistoryRepository(db_path=test_db_path)
    test_question_repo = LocalQuestionRepository()

    # Mock Qdrant store
    mock_vector_store = MagicMock(spec=QdrantVectorStore)
    mock_vector_store.count.return_value = 25
    mock_vector_store.upsert_exam_questions.return_value = None

    # Test LLM provider
    test_llm_provider = GoogleGenAIProvider(api_key="AIzaSyTestInitialKey123456789")
    test_llm_provider.embed_batch = MagicMock(return_value=[[0.1] * 768 for _ in range(25)])  # type: ignore[method-assign]

    # Test Auth provider
    test_auth_provider = GoogleAuthProvider(
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret-salt",
        redirect_uri="http://localhost:8000/api/auth/callback",
        allowed_emails=["allowed@example.com"],
    )

    # Test settings
    test_settings = Settings(
        gemini_api_key="AIzaSyTestInitialKey123456789",
        auth_enabled=True,
        allowed_emails=["allowed@example.com"],
        google_client_id="test-client-id.apps.googleusercontent.com",
        google_client_secret="test-client-secret-salt",
        google_redirect_uri="http://localhost:8000/api/auth/callback",
        session_secret="test-session-secret-for-system-auth-testing",
    )

    test_rag_service = RAGService(
        vector_store=mock_vector_store,
        llm_provider=test_llm_provider,
        question_repo=test_question_repo,
    )

    app = create_app()
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_history_repository] = lambda: test_repo
    app.dependency_overrides[get_question_repository] = lambda: test_question_repo
    app.dependency_overrides[get_vector_store] = lambda: mock_vector_store
    app.dependency_overrides[get_llm_provider] = lambda: test_llm_provider
    app.dependency_overrides[get_auth_provider] = lambda: test_auth_provider
    app.dependency_overrides[get_rag_service] = lambda: test_rag_service

    with TestClient(app) as client:
        valid_token = test_auth_provider.generate_session_token("allowed@example.com")
        client.cookies.set("session_user", valid_token)
        env = {
            "client": client,
            "settings": test_settings,
            "repo": test_repo,
            "llm_provider": test_llm_provider,
            "auth_provider": test_auth_provider,
            "vector_store": mock_vector_store,
            "rag_service": test_rag_service,
            "question_repo": test_question_repo,
        }
        yield env

    app.dependency_overrides.clear()


# --- Scenario 1: System Settings & Masking ---
def test_scenario_1_system_settings_masked_and_empty_guard(system_and_auth_env: dict):
    """シナリオ 1: システム設定の取得と API キーの安全なマスク表示"""
    client: TestClient = system_and_auth_env["client"]
    settings: Settings = system_and_auth_env["settings"]

    res = client.get("/api/system/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["gemini_api_key_masked"] == "AIza...6789"
    assert data["vector_store_points_count"] == 25
    assert data["auth_enabled"] is True

    # 空文字境界値のテスト
    settings.gemini_api_key = ""
    res_empty = client.get("/api/system/settings")
    assert res_empty.status_code == 200
    assert res_empty.json()["gemini_api_key_masked"] == ""

    # 短い文字列境界値のテスト (<= 4 文字)
    settings.gemini_api_key = "ABCD"
    res_short = client.get("/api/system/settings")
    assert res_short.status_code == 200
    assert res_short.json()["gemini_api_key_masked"] == "****"


# --- Scenario 2: Dynamic API Key Update ---
def test_scenario_2_update_api_key_dynamically_and_validation(system_and_auth_env: dict):
    """シナリオ 2: API キーの動的更新とシングルトン波及およびバリデーション"""
    client: TestClient = system_and_auth_env["client"]
    settings: Settings = system_and_auth_env["settings"]
    llm_provider: GoogleGenAIProvider = system_and_auth_env["llm_provider"]

    new_key = "AIzaSyUpdatedKey987654321"
    res = client.post("/api/system/api-key", json={"api_key": new_key})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["gemini_api_key_masked"] == "AIza...4321"

    # シングルトン LLM Provider と Settings に同期反映されていることを検証
    assert llm_provider.api_key == new_key
    assert settings.gemini_api_key == new_key

    # 後続リクエストでも更新後のキーが反映されていること
    res_settings = client.get("/api/system/settings")
    assert res_settings.status_code == 200
    assert res_settings.json()["gemini_api_key_masked"] == "AIza...4321"

    # 空文字列などのバリデーション異常系 (422)
    res_invalid = client.post("/api/system/api-key", json={"api_key": ""})
    assert res_invalid.status_code == 422

    # 空白文字のみのバリデーション異常系 (422)
    res_whitespace = client.post("/api/system/api-key", json={"api_key": "   "})
    assert res_whitespace.status_code == 422


# --- Scenario 3: Qdrant Reindex All ---
def test_scenario_3_reindex_all_questions(system_and_auth_env: dict):
    """シナリオ 3: Qdrant 全問再インデックス"""
    client: TestClient = system_and_auth_env["client"]
    vector_store: MagicMock = system_and_auth_env["vector_store"]
    question_repo: LocalQuestionRepository = system_and_auth_env["question_repo"]

    res = client.post("/api/system/reindex")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["reindexed_count"] == len(question_repo.get_all_questions())
    assert vector_store.upsert_exam_questions.called


# --- Scenario 4: Google OAuth Lifecycle & HMAC Cookie Protection ---
def test_scenario_4_oauth_lifecycle_and_hmac_protection(system_and_auth_env: dict):
    """シナリオ 4: Google OAuth 認証ライフサイクルおよび HMAC Cookie 改ざん遮断"""
    client: TestClient = system_and_auth_env["client"]
    settings: Settings = system_and_auth_env["settings"]
    auth_provider: GoogleAuthProvider = system_and_auth_env["auth_provider"]

    # Clear pre-authenticated cookies to start test from unauthenticated state
    client.cookies.clear()

    # 1. auth_enabled=False の場合、未認証でも authenticated: True
    settings.auth_enabled = False
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    assert res.json() == {"auth_enabled": False, "authenticated": True, "user_email": None}

    # 2. auth_enabled=True かつ未ログイン状態
    settings.auth_enabled = True
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    assert res.json() == {"auth_enabled": True, "authenticated": False, "user_email": None}

    # 3. 偽装平文 Cookie (SEC-001): 攻撃者が手動で平文メアドを付与
    client.cookies.set("session_user", "allowed@example.com")
    res_forged = client.get("/api/auth/status")
    assert res_forged.status_code == 200
    assert res_forged.json()["authenticated"] is False
    client.cookies.delete("session_user")

    # 4. 認可 URL 取得 (GET /api/auth/login)
    res_login = client.get("/api/auth/login")
    assert res_login.status_code == 200
    login_data = res_login.json()
    assert "accounts.google.com" in login_data["login_url"]
    valid_state = login_data["state"]

    # 5. 不正な state でのコールバック (403 Forbidden)
    res_invalid_state = client.get(
        "/api/auth/callback", params={"code": "dummy-code", "state": "invalid-state"}
    )
    assert res_invalid_state.status_code == 403

    # 5.1. ユーザーによる認可キャンセル (error=access_denied) (403 Forbidden)
    res_cancelled = client.get("/api/auth/callback", params={"error": "access_denied"})
    assert res_cancelled.status_code == 403

    # 6. 未許可メアドでのコールバック (403 Forbidden)
    auth_provider.exchange_code_for_user = MagicMock(return_value={"email": "attacker@evil.com"})  # type: ignore[method-assign]
    res_unauthorized = client.get(
        "/api/auth/callback", params={"code": "dummy-code", "state": valid_state}
    )
    assert res_unauthorized.status_code == 403

    # 7. 許可されたメアドでのコールバック (302 Found -> / リダイレクト & Cookie 発行)
    auth_provider.exchange_code_for_user = MagicMock(return_value={"email": "allowed@example.com"})  # type: ignore[method-assign]
    new_state = auth_provider.generate_state()
    res_callback = client.get(
        "/api/auth/callback",
        params={"code": "valid-auth-code", "state": new_state},
        follow_redirects=False,
    )
    assert res_callback.status_code == 302
    assert res_callback.headers["location"] == "/"
    assert "session_user" in res_callback.cookies
    signed_cookie = res_callback.cookies["session_user"]

    # 8. 署名付き Cookie を付与して status 確認 (認証成功)
    client.cookies.set("session_user", signed_cookie, domain="testserver", path="/")
    res_auth = client.get("/api/auth/status")
    assert res_auth.status_code == 200
    auth_status = res_auth.json()
    assert auth_status["auth_enabled"] is True
    assert auth_status["authenticated"] is True
    assert auth_status["user_email"] == "allowed@example.com"

    # 9. ログアウト (POST /api/auth/logout)
    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200
    assert res_logout.json()["success"] is True

    # ログアウト後の status 確認 (未認証に戻る)
    res_after_logout = client.get("/api/auth/status")
    assert res_after_logout.status_code == 200
    assert res_after_logout.json()["authenticated"] is False


def test_scenario_4_secure_cookie_handling(system_and_auth_env: dict):
    """シナリオ 4 補足: cookie_secure=True または HTTPS リクエスト時の Secure 属性付与 (CWE-614 防御)"""
    client: TestClient = system_and_auth_env["client"]
    settings: Settings = system_and_auth_env["settings"]
    auth_provider: GoogleAuthProvider = system_and_auth_env["auth_provider"]

    auth_provider.exchange_code_for_user = MagicMock(return_value={"email": "allowed@example.com"})  # type: ignore[method-assign]
    state = auth_provider.generate_state()

    # 1. settings.cookie_secure = True の場合
    settings.cookie_secure = True
    res = client.get(
        "/api/auth/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert res.status_code == 302
    set_cookie_header = res.headers.get("set-cookie", "")
    assert "secure" in set_cookie_header.lower()

    # 2. settings.cookie_secure = False だが HTTPS リクエストの場合
    settings.cookie_secure = False
    state_https = auth_provider.generate_state()
    res_https = client.get(
        "https://testserver/api/auth/callback",
        params={"code": "auth-code", "state": state_https},
        follow_redirects=False,
    )
    assert res_https.status_code == 302
    set_cookie_https = res_https.headers.get("set-cookie", "")
    assert "secure" in set_cookie_https.lower()


# --- Scenario 5: Reset Practice History ---
def test_scenario_5_reset_practice_history(system_and_auth_env: dict):
    """シナリオ 5: 学習履歴および演習セッションのリセット"""
    client: TestClient = system_and_auth_env["client"]
    repo: SQLitePracticeHistoryRepository = system_and_auth_env["repo"]
    question_repo: LocalQuestionRepository = system_and_auth_env["question_repo"]

    # 1. 練習履歴とセッションを投入
    practice_service = PracticeService(question_repo=question_repo, history_repo=repo)
    practice_service.submit_answer(
        question_id="2025-SA-AM2-Q01",
        choice_key=AnswerKey("イ"),
        time_spent_seconds=10.0,
    )
    session = DojoSessionState(
        session_id="test-session-001",
        mode=DojoMode.ALL,
        question_ids=["2025-SA-AM2-Q01", "2025-SA-AM2-Q02"],
        current_index=0,
        total_count=2,
    )
    repo.save_session_state(session)

    # 投入されたことを確認
    assert len(repo.get_attempts(limit=10)) == 1
    assert repo.get_active_session() is not None

    # 2. リセット API 呼び出し
    res = client.post("/api/system/reset-history")
    assert res.status_code == 200
    assert res.json()["success"] is True

    # 3. 履歴およびセッションが消去されていることを直接検証
    assert len(repo.get_attempts(limit=10)) == 0
    assert repo.get_active_session() is None
