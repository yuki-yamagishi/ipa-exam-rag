"""Tests for Dojo Session & Practice Submission API (Issue #013 / DoD-B2)."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.domain.models import DojoMode, DojoSessionConfig
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.presentation.api.deps import get_history_repository, require_authenticated_user
from src.presentation.api.main import create_app


@pytest.fixture
def practice_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """TestClient configured with an isolated temporary SQLite database."""
    test_db_path = tmp_path / "test_practice.db"
    test_repo = SQLitePracticeHistoryRepository(db_path=test_db_path)

    app = create_app()
    app.dependency_overrides[get_history_repository] = lambda: test_repo

    with TestClient(app) as client:
        client.test_repo = test_repo  # type: ignore[attr-defined]
        yield client

    app.dependency_overrides.clear()


# --- Scenario 1: Submit Answer Correct ---
def test_scenario_1_submit_answer_correct(practice_client: TestClient):
    """シナリオ 1: 設問解答の判定および SQLite 永続化 (正常系)"""
    payload = {
        "question_id": "2025-SA-AM2-Q01",
        "choice_key": "エ",
        "time_spent_seconds": 12.5,
    }
    res = practice_client.post("/api/practice/submit", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_correct"] is True
    assert data["correct_answer"] == "エ"
    assert data["user_choice"] == "エ"
    assert data["question_id"] == "2025-SA-AM2-Q01"
    assert data["attempt_id"] is not None

    # SQLite practice_attempts 永続化副作用の直接検証
    repo: SQLitePracticeHistoryRepository = practice_client.test_repo
    attempts = repo.get_attempts(limit=10)
    assert len(attempts) == 1
    assert attempts[0].id == data["attempt_id"]
    assert attempts[0].question_id == "2025-SA-AM2-Q01"
    assert attempts[0].is_correct is True
    assert attempts[0].time_spent_seconds == 12.5


# --- Scenario 2: Submit Answer Incorrect ---
def test_scenario_2_submit_answer_incorrect(practice_client: TestClient):
    """シナリオ 2: 誤答時の判定および SQLite 永続化"""
    payload = {
        "question_id": "2025-SA-AM2-Q01",
        "choice_key": "ア",
        "time_spent_seconds": 8.0,
    }
    res = practice_client.post("/api/practice/submit", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_correct"] is False
    assert data["correct_answer"] == "エ"
    assert data["user_choice"] == "ア"
    assert data["question_id"] == "2025-SA-AM2-Q01"
    assert data["attempt_id"] is not None

    # SQLite practice_attempts 永続化副作用の直接検証
    repo: SQLitePracticeHistoryRepository = practice_client.test_repo
    attempts = repo.get_attempts(limit=10)
    assert len(attempts) == 1
    assert attempts[0].id == data["attempt_id"]
    assert attempts[0].question_id == "2025-SA-AM2-Q01"
    assert attempts[0].is_correct is False
    assert attempts[0].time_spent_seconds == 8.0


# --- Scenario 3: Submit Answer Question Not Found ---
def test_scenario_3_submit_answer_not_found(practice_client: TestClient):
    """シナリオ 3: 存在しない設問に対する解答送信 (異常系)"""
    payload = {
        "question_id": "INVALID-Q999",
        "choice_key": "ア",
        "time_spent_seconds": 5.0,
    }
    res = practice_client.post("/api/practice/submit", json=payload)
    assert res.status_code == 404
    err = res.json()
    assert "detail" in err
    assert "Question not found: INVALID-Q999" in err["detail"]


# --- Scenario 4: Create Dojo Session Success ---
def test_scenario_4_create_dojo_session_success(practice_client: TestClient):
    """シナリオ 4: 道場セッションの新規作成 (正常系)"""
    config = DojoSessionConfig(
        mode=DojoMode.ALL,
        year=2025,
        question_count=5,
        shuffle=False,
        user_email="test@example.com",
    )
    res = practice_client.post("/api/practice/sessions", json=config.model_dump())
    assert res.status_code == 201
    data = res.json()
    assert "session" in data
    assert "questions" in data
    assert len(data["questions"]) == 5
    assert data["session"]["current_index"] == 0
    assert data["session"]["is_completed"] is False
    assert len(data["session"]["question_ids"]) == 5
    assert data["session"]["session_id"] is not None


# --- Scenario 5: Create Dojo Session 0 Questions Boundary ---
def test_scenario_5_create_session_zero_questions_boundary(practice_client: TestClient):
    """シナリオ 5: 条件合致設問が 0 件の場合のセッション作成拒絶 (境界値・異常系)"""
    config = DojoSessionConfig(
        mode=DojoMode.ALL,
        year=1990,  # Non-existent year
        question_count=5,
    )
    res = practice_client.post("/api/practice/sessions", json=config.model_dump())
    assert res.status_code == 400
    err = res.json()
    assert "detail" in err
    assert "No questions match the specified session criteria" in err["detail"]


# --- Scenario 6 & 7: Active Resumable Session Fetching ---
def test_scenario_7_get_active_session_when_empty(practice_client: TestClient):
    """シナリオ 7: 中断セッションが存在しない場合の取得 (境界値・空状態)"""
    res = practice_client.get("/api/practice/sessions/active?user_email=nobody@example.com")
    assert res.status_code == 200
    data = res.json()
    assert data["session"] is None
    assert data["questions"] == []


def test_scenario_6_get_active_session_resumable(practice_client: TestClient):
    """シナリオ 6: 中断セッションの取得および再開 (正常系)"""
    # Create session first
    config = DojoSessionConfig(
        mode=DojoMode.ALL,
        year=2025,
        question_count=3,
        shuffle=False,
        user_email="user1@example.com",
    )
    create_res = practice_client.post("/api/practice/sessions", json=config.model_dump())
    assert create_res.status_code == 201
    created_sess = create_res.json()["session"]

    # Fetch active session
    res = practice_client.get("/api/practice/sessions/active?user_email=user1@example.com")
    assert res.status_code == 200
    active_data = res.json()
    assert active_data["session"] is not None
    assert active_data["session"]["session_id"] == created_sess["session_id"]
    assert len(active_data["questions"]) == 3


# --- Scenario 8: Update Session Progress (Autosave) ---
def test_scenario_8_update_session_progress(practice_client: TestClient):
    """シナリオ 8: セッション進捗の更新保存 (オートセーブ正常系)"""
    config = DojoSessionConfig(
        mode=DojoMode.ALL,
        year=2025,
        question_count=3,
        user_email="user1@example.com",
    )
    create_res = practice_client.post("/api/practice/sessions", json=config.model_dump())
    sess_id = create_res.json()["session"]["session_id"]

    progress_payload = {
        "current_index": 2,
        "results": [{"question_id": "2025-SA-AM2-Q01", "is_correct": True}],
    }
    prog_res = practice_client.post(
        f"/api/practice/sessions/{sess_id}/progress", json=progress_payload
    )
    assert prog_res.status_code == 200
    assert prog_res.json() == {"status": "saved"}

    # Verify active session now reflects updated current_index and results
    active_res = practice_client.get("/api/practice/sessions/active?user_email=user1@example.com")
    assert active_res.status_code == 200
    updated_sess = active_res.json()["session"]
    assert updated_sess["current_index"] == 2
    assert len(updated_sess["results"]) == 1
    assert updated_sess["updated_at"] >= create_res.json()["session"]["updated_at"]


# --- Scenario 9: Non-existent Session ID 404 Guard ---
def test_scenario_9_non_existent_session_id_404(practice_client: TestClient):
    """シナリオ 9: 存在しないセッション ID 操作時の 404 エラー返却 (異常系)"""
    non_existent = "INVALID-SESS-999"

    # Progress
    res1 = practice_client.post(
        f"/api/practice/sessions/{non_existent}/progress",
        json={"current_index": 1, "results": []},
    )
    assert res1.status_code == 404
    assert f"Session not found: {non_existent}" in res1.json()["detail"]

    # Complete
    res2 = practice_client.post(f"/api/practice/sessions/{non_existent}/complete")
    assert res2.status_code == 404
    assert f"Session not found: {non_existent}" in res2.json()["detail"]

    # Abandon
    res3 = practice_client.delete(f"/api/practice/sessions/{non_existent}")
    assert res3.status_code == 404
    assert f"Session not found: {non_existent}" in res3.json()["detail"]


# --- Scenario 10: Complete and Abandon Session ---
def test_scenario_10_complete_and_abandon_session(practice_client: TestClient):
    """シナリオ 10: セッションの完了および破棄"""
    # 1. Test Complete
    config1 = DojoSessionConfig(
        mode=DojoMode.ALL,
        year=2025,
        question_count=2,
        user_email="comp@example.com",
    )
    c_res1 = practice_client.post("/api/practice/sessions", json=config1.model_dump())
    sess1_id = c_res1.json()["session"]["session_id"]

    comp_res = practice_client.post(f"/api/practice/sessions/{sess1_id}/complete")
    assert comp_res.status_code == 200
    assert comp_res.json() == {"status": "completed"}

    # Active session should now be empty
    after_comp = practice_client.get("/api/practice/sessions/active?user_email=comp@example.com")
    assert after_comp.json()["session"] is None

    # 2. Test Abandon (Delete)
    config2 = DojoSessionConfig(
        mode=DojoMode.ALL,
        year=2025,
        question_count=2,
        user_email="aband@example.com",
    )
    c_res2 = practice_client.post("/api/practice/sessions", json=config2.model_dump())
    sess2_id = c_res2.json()["session"]["session_id"]

    aband_res = practice_client.delete(f"/api/practice/sessions/{sess2_id}")
    assert aband_res.status_code == 200
    assert aband_res.json() == {"status": "abandoned"}

    # Active session should now be empty
    after_aband = practice_client.get("/api/practice/sessions/active?user_email=aband@example.com")
    assert after_aband.json()["session"] is None


# --- Scenario 11: Multi-tenant Session Ownership Authorization Guard (403 Forbidden) ---
def test_scenario_11_session_ownership_authorization_guard(practice_client: TestClient):
    """シナリオ 11: 他人のセッションに対する progress / complete / abandon の操作拒絶 (403 Forbidden)"""
    # 1. ユーザー victim がセッションを作成
    config = DojoSessionConfig(
        mode=DojoMode.ALL,
        year=2025,
        question_count=3,
        user_email="victim@example.com",
    )
    c_res = practice_client.post("/api/practice/sessions", json=config.model_dump())
    assert c_res.status_code == 201
    sess_id = c_res.json()["session"]["session_id"]
    assert c_res.json()["session"]["user_email"] == "victim@example.com"

    # 2. 攻撃者 attacker として require_authenticated_user をモック
    practice_client.app.dependency_overrides[require_authenticated_user] = (  # type: ignore[attr-defined]
        lambda: "attacker@example.com"
    )

    try:
        # 2a. 進捗更新の不正操作 -> 403
        progress_res = practice_client.post(
            f"/api/practice/sessions/{sess_id}/progress",
            json={"current_index": 1, "results": []},
        )
        assert progress_res.status_code == 403
        assert "この演習セッションを操作する権限がありません。" in progress_res.json()["detail"]

        # 2b. 完了処理の不正操作 -> 403
        complete_res = practice_client.post(f"/api/practice/sessions/{sess_id}/complete")
        assert complete_res.status_code == 403
        assert "この演習セッションを操作する権限がありません。" in complete_res.json()["detail"]

        # 2c. 破棄処理の不正操作 -> 403
        abandon_res = practice_client.delete(f"/api/practice/sessions/{sess_id}")
        assert abandon_res.status_code == 403
        assert "この演習セッションを操作する権限がありません。" in abandon_res.json()["detail"]

        # 3. 正当な所有者 victim として実行した場合は正常に完了できること
        practice_client.app.dependency_overrides[require_authenticated_user] = (  # type: ignore[attr-defined]
            lambda: "victim@example.com"
        )
        legit_res = practice_client.post(f"/api/practice/sessions/{sess_id}/complete")
        assert legit_res.status_code == 200
        assert legit_res.json() == {"status": "completed"}
    finally:
        # クリーンアップ
        practice_client.app.dependency_overrides.pop(require_authenticated_user, None)  # type: ignore[attr-defined]

