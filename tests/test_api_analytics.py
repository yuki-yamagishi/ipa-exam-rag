"""Comprehensive integration tests for Analytics Dashboard API (ISSUE-014 / DoD-B3)."""

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.domain.models import (
    AnswerKey,
    ExamChoice,
    ExamQuestion,
    PracticeAttempt,
)
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.presentation.api.deps import (
    get_history_repository,
    get_question_repository,
)
from src.presentation.api.main import create_app


class MockQuestionRepository:
    """Hermetic in-memory mock repository for exam questions."""

    def __init__(self, questions: list[ExamQuestion] | None = None) -> None:
        self.questions = questions or []
        self._map = {q.id: q for q in self.questions}

    def get_all_questions(self) -> list[ExamQuestion]:
        return list(self.questions)

    def get_question_by_id(self, question_id: str) -> ExamQuestion | None:
        return self._map.get(question_id)


def create_sample_questions() -> list[ExamQuestion]:
    """Provide deterministic test question fixtures."""
    return [
        ExamQuestion(
            id="2025-SA-AM2-Q01",
            year=2025,
            term="秋期",
            exam_type="SA",
            question_number=1,
            category="テクノロジ系",
            question_text="コンパイラの構文解析処理に関する記述として適切なものはどれか。",
            choices=[
                ExamChoice(key=AnswerKey.A, text="選択肢ア"),
                ExamChoice(key=AnswerKey.I, text="選択肢イ"),
                ExamChoice(key=AnswerKey.U, text="選択肢ウ"),
                ExamChoice(key=AnswerKey.E, text="選択肢エ"),
            ],
            correct_answer=AnswerKey.I,
            explanation="コンパイラの構文解析に関する解説です。",
        ),
        ExamQuestion(
            id="2025-SA-AM2-Q02",
            year=2025,
            term="秋期",
            exam_type="SA",
            question_number=2,
            category="マネジメント系",
            question_text="プロジェクトマネジメントのEVMにおけるCPIの説明はどれか。",
            choices=[
                ExamChoice(key=AnswerKey.A, text="選択肢ア"),
                ExamChoice(key=AnswerKey.I, text="選択肢イ"),
                ExamChoice(key=AnswerKey.U, text="選択肢ウ"),
                ExamChoice(key=AnswerKey.E, text="選択肢エ"),
            ],
            correct_answer=AnswerKey.U,
            explanation="EVMにおけるCPI（コスト効率指数）の解説です。",
        ),
    ]


@pytest.fixture
def analytics_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """TestClient configured with isolated SQLite database and mock question repo."""
    test_db_path = tmp_path / "test_analytics.db"
    test_repo = SQLitePracticeHistoryRepository(db_path=test_db_path)
    mock_questions = create_sample_questions()
    mock_repo = MockQuestionRepository(mock_questions)

    app = create_app()
    app.dependency_overrides[get_history_repository] = lambda: test_repo
    app.dependency_overrides[get_question_repository] = lambda: mock_repo

    try:
        with TestClient(app) as client:
            client.test_repo = test_repo  # type: ignore[attr-defined]
            client.mock_repo = mock_repo  # type: ignore[attr-defined]
            yield client
    finally:
        app.dependency_overrides.clear()


# --- Scenario 1: Summary Statistics (Normal / With History) ---
def test_scenario_1_summary_with_history(analytics_client: TestClient):
    """シナリオ 1: サマリー統計の取得 (正常系 / 履歴あり)"""
    repo: SQLitePracticeHistoryRepository = analytics_client.test_repo

    # Insert 3 attempts: 2 correct, 1 incorrect across 2 questions
    repo.record_attempt(
        PracticeAttempt(
            id=str(uuid.uuid4()),
            question_id="2025-SA-AM2-Q01",
            question_number=1,
            category="テクノロジ系",
            user_choice=AnswerKey.I,
            correct_answer=AnswerKey.I,
            is_correct=True,
            time_spent_seconds=15.0,
            session_id="sess-01",
        )
    )
    repo.record_attempt(
        PracticeAttempt(
            id=str(uuid.uuid4()),
            question_id="2025-SA-AM2-Q01",
            question_number=1,
            category="テクノロジ系",
            user_choice=AnswerKey.I,
            correct_answer=AnswerKey.I,
            is_correct=True,
            time_spent_seconds=10.0,
            session_id="sess-01",
        )
    )
    repo.record_attempt(
        PracticeAttempt(
            id=str(uuid.uuid4()),
            question_id="2025-SA-AM2-Q02",
            question_number=2,
            category="マネジメント系",
            user_choice=AnswerKey.A,
            correct_answer=AnswerKey.U,
            is_correct=False,
            time_spent_seconds=20.0,
            session_id="sess-02",
        )
    )

    res = analytics_client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_attempts"] == 3
    assert data["correct_attempts"] == 2
    assert abs(data["accuracy_rate"] - (2 / 3)) < 0.001
    assert data["distinct_questions_attempted"] == 2
    assert data["total_sessions"] == 2


# --- Scenario 2: Summary Statistics (Boundary / Zero History Initial State) ---
def test_scenario_2_summary_initial_empty_state(analytics_client: TestClient):
    """シナリオ 2: サマリー統計の取得 (境界系 / 履歴0件の初期状態)"""
    res = analytics_client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_attempts"] == 0
    assert data["correct_attempts"] == 0
    assert data["accuracy_rate"] == 0.0
    assert data["distinct_questions_attempted"] == 0
    assert data["total_sessions"] == 0


# --- Scenario 3: Category Performance Statistics (Normal) ---
def test_scenario_3_category_performance(analytics_client: TestClient):
    """シナリオ 3: 分野別習熟度統計の取得 (正常系)"""
    repo: SQLitePracticeHistoryRepository = analytics_client.test_repo

    repo.record_attempt(
        PracticeAttempt(
            id=str(uuid.uuid4()),
            question_id="2025-SA-AM2-Q01",
            question_number=1,
            category="テクノロジ系",
            user_choice=AnswerKey.I,
            correct_answer=AnswerKey.I,
            is_correct=True,
            time_spent_seconds=12.0,
        )
    )
    repo.record_attempt(
        PracticeAttempt(
            id=str(uuid.uuid4()),
            question_id="2025-SA-AM2-Q02",
            question_number=2,
            category="マネジメント系",
            user_choice=AnswerKey.A,
            correct_answer=AnswerKey.U,
            is_correct=False,
            time_spent_seconds=18.0,
        )
    )

    res = analytics_client.get("/api/analytics/categories")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    cat_map = {item["category"]: item for item in data}
    assert cat_map["テクノロジ系"]["total_attempts"] == 1
    assert cat_map["テクノロジ系"]["accuracy_rate"] == 1.0
    assert cat_map["マネジメント系"]["total_attempts"] == 1
    assert cat_map["マネジメント系"]["accuracy_rate"] == 0.0


# --- Scenario 4: Weak Categories with Threshold Filtering (Normal) ---
def test_scenario_4_weak_categories(analytics_client: TestClient):
    """シナリオ 4: 苦手分野の抽出 (正常系 / しきい値指定)"""
    repo: SQLitePracticeHistoryRepository = analytics_client.test_repo

    # テクノロジ系: 2 attempts, 1 correct -> 50%
    repo.record_attempt(
        PracticeAttempt(
            id=str(uuid.uuid4()),
            question_id="2025-SA-AM2-Q01",
            question_number=1,
            category="テクノロジ系",
            user_choice=AnswerKey.I,
            correct_answer=AnswerKey.I,
            is_correct=True,
        )
    )
    repo.record_attempt(
        PracticeAttempt(
            id=str(uuid.uuid4()),
            question_id="2025-SA-AM2-Q01",
            question_number=1,
            category="テクノロジ系",
            user_choice=AnswerKey.A,
            correct_answer=AnswerKey.I,
            is_correct=False,
        )
    )
    # マネジメント系: 1 attempt, 1 correct -> 100%
    repo.record_attempt(
        PracticeAttempt(
            id=str(uuid.uuid4()),
            question_id="2025-SA-AM2-Q02",
            question_number=2,
            category="マネジメント系",
            user_choice=AnswerKey.U,
            correct_answer=AnswerKey.U,
            is_correct=True,
        )
    )

    # Filter with max_accuracy=0.6: only テクノロジ系 (50%) should match
    res = analytics_client.get("/api/analytics/weak-categories?max_accuracy=0.6")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["category"] == "テクノロジ系"
    assert data[0]["accuracy_rate"] == 0.5


# --- Scenario 5: Weak Questions with Question Details Enrichment (Normal) ---
def test_scenario_5_weak_questions_enrichment(analytics_client: TestClient):
    """シナリオ 5: 要復習問題ランキングの取得 (正常系 / 問題文エンリッチ)"""
    repo: SQLitePracticeHistoryRepository = analytics_client.test_repo

    # Record incorrect attempt on Q02
    repo.record_attempt(
        PracticeAttempt(
            id=str(uuid.uuid4()),
            question_id="2025-SA-AM2-Q02",
            question_number=2,
            category="マネジメント系",
            user_choice=AnswerKey.A,
            correct_answer=AnswerKey.U,
            is_correct=False,
            time_spent_seconds=25.0,
        )
    )

    res = analytics_client.get("/api/analytics/weak-questions?limit=3")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    weak = data[0]
    assert weak["question_id"] == "2025-SA-AM2-Q02"
    assert weak["incorrect_count"] == 1
    assert weak["latest_is_correct"] is False
    assert "EVM" in weak["question_text"]
    assert weak["category"] == "マネジメント系"


# --- Scenario 6: Recent Practice History (Normal / Limit) ---
def test_scenario_6_recent_history(analytics_client: TestClient):
    """シナリオ 6: 直近解答履歴の取得 (正常系 / 件数制限)"""
    repo: SQLitePracticeHistoryRepository = analytics_client.test_repo

    for i in range(8):
        repo.record_attempt(
            PracticeAttempt(
                id=f"att-{i:02d}",
                question_id="2025-SA-AM2-Q01",
                question_number=1,
                category="テクノロジ系",
                user_choice=AnswerKey.I,
                correct_answer=AnswerKey.I,
                is_correct=True,
                time_spent_seconds=float(i + 1),
            )
        )

    res = analytics_client.get("/api/analytics/history?limit=5")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 5
    # Order should be descending (most recent first)
    assert data[0]["id"] == "att-07"


# --- Scenario 7: Query Parameter Validation (Abnormal / 422) ---
def test_scenario_7_invalid_query_parameters(analytics_client: TestClient):
    """シナリオ 7: 不正なクエリパラメータの境界値バリデーション (異常系)"""
    # limit=0 for weak-questions (ge=1)
    res1 = analytics_client.get("/api/analytics/weak-questions?limit=0")
    assert res1.status_code == 422

    # limit=51 for weak-questions (le=50)
    res2 = analytics_client.get("/api/analytics/weak-questions?limit=51")
    assert res2.status_code == 422

    # limit=0 for history (ge=1)
    res3_zero = analytics_client.get("/api/analytics/history?limit=0")
    assert res3_zero.status_code == 422

    # limit=101 for history (le=100)
    res3 = analytics_client.get("/api/analytics/history?limit=101")
    assert res3.status_code == 422

    # max_accuracy=-0.1 for weak-categories (ge=0.0)
    res4 = analytics_client.get("/api/analytics/weak-categories?max_accuracy=-0.1")
    assert res4.status_code == 422

    # max_accuracy=1.1 for weak-categories (le=1.0)
    res5 = analytics_client.get("/api/analytics/weak-categories?max_accuracy=1.1")
    assert res5.status_code == 422
