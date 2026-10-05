"""Tests for resumable dojo practice sessions and SQLite V3 migration."""

import sqlite3
from unittest.mock import MagicMock

import pytest

from src.application.practice_service import PracticeService
from src.domain.models import (
    AnswerKey,
    DojoMode,
    DojoSessionConfig,
    DojoSessionState,
    ExamChoice,
    ExamQuestion,
)
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.infrastructure.migrations.migrator import SchemaMigrator
from src.infrastructure.migrations.versions import _migrate_v3


@pytest.fixture
def in_memory_repo() -> SQLitePracticeHistoryRepository:
    """Create an in-memory repository with all migrations applied."""
    repo = SQLitePracticeHistoryRepository(db_path=":memory:")
    yield repo
    repo.close()


@pytest.fixture
def mock_questions() -> list[ExamQuestion]:
    """Create a sample question queue for testing."""
    return [
        ExamQuestion(
            id=f"q_{i}",
            exam_type="SA",
            year=2025,
            term="秋期",
            question_number=i,
            category="システムアーキテクチャ",
            keywords=["キーワード"],
            question_text=f"問題文 {i}",
            choices=[
                ExamChoice(key=AnswerKey.A, text="選択肢ア"),
                ExamChoice(key=AnswerKey.I, text="選択肢イ"),
                ExamChoice(key=AnswerKey.U, text="選択肢ウ"),
                ExamChoice(key=AnswerKey.E, text="選択肢エ"),
            ],
            correct_answer=AnswerKey.U,
            explanation=f"解説 {i}",
        )
        for i in range(1, 6)
    ]


def test_schema_migration_v3_creates_dojo_sessions_table() -> None:
    """Verify that V3 migration creates dojo_sessions table and indexes cleanly."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        # Apply full migrations up to V3
        migrator = SchemaMigrator()
        migrator.apply_all(conn)

        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dojo_sessions';"
        )
        assert cursor.fetchone() is not None, "dojo_sessions table must exist"

        cursor.execute("PRAGMA table_info(dojo_sessions);")
        cols = {row["name"] for row in cursor.fetchall()}
        expected_cols = {
            "session_id",
            "user_email",
            "mode",
            "year",
            "category",
            "question_count",
            "shuffle",
            "question_ids",
            "current_index",
            "results_json",
            "is_completed",
            "created_at",
            "updated_at",
        }
        assert expected_cols.issubset(cols), (
            f"Missing columns in dojo_sessions: {expected_cols - cols}"
        )

        # Test idempotency of V3
        _migrate_v3(conn)
    finally:
        conn.close()


def test_history_repository_session_lifecycle(
    in_memory_repo: SQLitePracticeHistoryRepository,
) -> None:
    """Verify session save, retrieval, completion, and deletion in repository."""
    session = DojoSessionState(
        session_id="sess-001",
        user_email="student@example.com",
        mode=DojoMode.CATEGORY,
        year=2025,
        category="ネットワーク",
        question_count=5,
        shuffle=True,
        question_ids=["q_1", "q_2", "q_3", "q_4", "q_5"],
        current_index=1,
        results=[
            {"question_id": "q_1", "is_correct": True, "user_choice": "ウ", "correct_answer": "ウ"}
        ],
        is_completed=False,
    )

    # 1. Save session
    in_memory_repo.save_session_state(session)

    # 2. Get active session
    active = in_memory_repo.get_active_session(user_email="student@example.com")
    assert active is not None
    assert active.session_id == "sess-001"
    assert active.category == "ネットワーク"
    assert active.current_index == 1
    assert len(active.results) == 1
    assert active.question_ids == ["q_1", "q_2", "q_3", "q_4", "q_5"]
    assert not active.is_completed

    # 3. Update session progress (e.g. solved question 2)
    session.current_index = 2
    session.results.append(
        {"question_id": "q_2", "is_correct": False, "user_choice": "ア", "correct_answer": "ウ"}
    )
    in_memory_repo.save_session_state(session)

    updated = in_memory_repo.get_active_session(user_email="student@example.com")
    assert updated is not None
    assert updated.current_index == 2
    assert len(updated.results) == 2

    # 4. Mark session completed
    in_memory_repo.mark_session_completed("sess-001")
    assert in_memory_repo.get_active_session(user_email="student@example.com") is None

    # 5. Delete session
    in_memory_repo.delete_session("sess-001")
    assert in_memory_repo.get_active_session(user_email="student@example.com") is None


def test_multi_user_session_isolation(in_memory_repo: SQLitePracticeHistoryRepository) -> None:
    """Verify that sessions are strictly isolated between different user emails."""
    sess_a = DojoSessionState(
        session_id="sess-user-a",
        user_email="alice@example.com",
        question_ids=["q_1", "q_2"],
        current_index=1,
        is_completed=False,
    )
    sess_b = DojoSessionState(
        session_id="sess-user-b",
        user_email="bob@example.com",
        question_ids=["q_3", "q_4"],
        current_index=0,
        is_completed=False,
    )

    in_memory_repo.save_session_state(sess_a)
    in_memory_repo.save_session_state(sess_b)

    active_a = in_memory_repo.get_active_session(user_email="alice@example.com")
    active_b = in_memory_repo.get_active_session(user_email="bob@example.com")

    assert active_a is not None and active_a.session_id == "sess-user-a"
    assert active_b is not None and active_b.session_id == "sess-user-b"
    assert in_memory_repo.get_active_session(user_email="charlie@example.com") is None


def test_practice_service_resume_and_abandon(
    in_memory_repo: SQLitePracticeHistoryRepository, mock_questions: list[ExamQuestion]
) -> None:
    """Verify PracticeService session workflow: save, query resumable, resume, and abandon."""
    mock_q_repo = MagicMock()
    mock_q_repo.get_all_questions.return_value = mock_questions

    service = PracticeService(question_repo=mock_q_repo, history_repo=in_memory_repo)

    # 1. Create a session queue
    cfg = DojoSessionConfig(mode=DojoMode.ALL, question_count=5, shuffle=False)
    queue = service.create_dojo_session(cfg)
    assert len(queue) == 5

    session_id = "test-session-xyz"
    session_state = DojoSessionState(
        session_id=session_id,
        user_email="learner@example.com",
        mode=cfg.mode,
        question_count=cfg.question_count,
        shuffle=cfg.shuffle,
        question_ids=[q.id for q in queue],
        current_index=0,
        results=[],
        is_completed=False,
    )

    # Save initial progress
    service.save_session_progress(session_state)

    # Check resumable
    resumable = service.get_resumable_session(user_email="learner@example.com")
    assert resumable is not None
    assert resumable.session_id == session_id

    # Answer question 1 and update progress
    session_state.current_index = 1
    session_state.results.append(
        {"question_id": "q_1", "is_correct": True, "user_choice": "ウ", "correct_answer": "ウ"}
    )
    service.save_session_progress(session_state)

    # Resume session
    resumed = service.resume_dojo_session(session_id, user_email="learner@example.com")
    assert resumed is not None
    res_state, res_queue = resumed
    assert res_state.current_index == 1
    assert len(res_state.results) == 1
    assert [q.id for q in res_queue] == ["q_1", "q_2", "q_3", "q_4", "q_5"]

    # Abandon session
    service.abandon_session(session_id)
    assert service.get_resumable_session(user_email="learner@example.com") is None
    assert service.resume_dojo_session(session_id, user_email="learner@example.com") is None
