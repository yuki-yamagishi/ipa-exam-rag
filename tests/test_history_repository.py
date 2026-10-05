"""Unit tests for SQLitePracticeHistoryRepository."""

import tempfile
from pathlib import Path

import pytest

from src.domain.models import AnswerKey, PracticeAttempt
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository


@pytest.fixture
def temp_db_repo():
    """Create a repository backed by a temporary SQLite file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_history.db"
        repo = SQLitePracticeHistoryRepository(db_path=db_path)
        try:
            yield repo
        finally:
            repo.close()


def test_record_and_get_attempts(temp_db_repo: SQLitePracticeHistoryRepository):
    repo = temp_db_repo

    attempt = PracticeAttempt(
        id="attempt-1",
        session_id="session-1",
        question_id="2025-SA-AM2-Q01",
        exam_type="SA",
        year=2025,
        term="秋期",
        question_number=1,
        category="システムアーキテクチャ設計",
        user_choice=AnswerKey.I,
        correct_answer=AnswerKey.I,
        is_correct=True,
        time_spent_seconds=12.5,
        answered_at="2026-09-15T12:00:00Z",
    )
    repo.record_attempt(attempt)

    attempts = repo.get_attempts()
    assert len(attempts) == 1
    assert attempts[0].id == "attempt-1"
    assert attempts[0].is_correct is True
    assert attempts[0].user_choice == AnswerKey.I

    # Filter by question_id
    q1_attempts = repo.get_attempts(question_id="2025-SA-AM2-Q01")
    assert len(q1_attempts) == 1
    q2_attempts = repo.get_attempts(question_id="NON_EXISTENT")
    assert len(q2_attempts) == 0


def test_latest_attempt_per_question(temp_db_repo: SQLitePracticeHistoryRepository):
    repo = temp_db_repo

    # Attempt 1: Question 1 Incorrect
    repo.record_attempt(
        PracticeAttempt(
            id="attempt-1",
            question_id="2025-SA-AM2-Q01",
            question_number=1,
            category="システムアーキテクチャ設計",
            user_choice=AnswerKey.A,
            correct_answer=AnswerKey.I,
            is_correct=False,
            answered_at="2026-09-15T10:00:00Z",
        )
    )

    # Attempt 2: Question 1 Correct (Later attempt)
    repo.record_attempt(
        PracticeAttempt(
            id="attempt-2",
            question_id="2025-SA-AM2-Q01",
            question_number=1,
            category="システムアーキテクチャ設計",
            user_choice=AnswerKey.I,
            correct_answer=AnswerKey.I,
            is_correct=True,
            answered_at="2026-09-15T11:00:00Z",
        )
    )

    # Attempt 3: Question 2 Incorrect
    repo.record_attempt(
        PracticeAttempt(
            id="attempt-3",
            question_id="2025-SA-AM2-Q02",
            question_number=2,
            category="セキュリティ",
            user_choice=AnswerKey.U,
            correct_answer=AnswerKey.E,
            is_correct=False,
            answered_at="2026-09-15T11:30:00Z",
        )
    )

    latest_map = repo.get_latest_attempt_per_question()
    assert len(latest_map) == 2
    # Q1 latest must be correct
    assert latest_map["2025-SA-AM2-Q01"].id == "attempt-2"
    assert latest_map["2025-SA-AM2-Q01"].is_correct is True
    # Q2 latest must be incorrect
    assert latest_map["2025-SA-AM2-Q02"].id == "attempt-3"
    assert latest_map["2025-SA-AM2-Q02"].is_correct is False


def test_statistics_and_weak_questions(temp_db_repo: SQLitePracticeHistoryRepository):
    repo = temp_db_repo

    # Record 3 attempts across 2 categories
    repo.record_attempt(
        PracticeAttempt(
            id="a1",
            session_id="s1",
            question_id="Q1",
            question_number=1,
            category="アーキテクチャ",
            user_choice=AnswerKey.I,
            correct_answer=AnswerKey.I,
            is_correct=True,
            answered_at="2026-09-15T10:00:00Z",
        )
    )
    repo.record_attempt(
        PracticeAttempt(
            id="a2",
            session_id="s1",
            question_id="Q2",
            question_number=2,
            category="セキュリティ",
            user_choice=AnswerKey.A,
            correct_answer=AnswerKey.I,
            is_correct=False,
            answered_at="2026-09-15T10:05:00Z",
        )
    )
    repo.record_attempt(
        PracticeAttempt(
            id="a3",
            session_id="s2",
            question_id="Q2",
            question_number=2,
            category="セキュリティ",
            user_choice=AnswerKey.U,
            correct_answer=AnswerKey.I,
            is_correct=False,
            answered_at="2026-09-15T11:00:00Z",
        )
    )

    # Category stats
    cat_stats = repo.get_category_stats()
    assert len(cat_stats) == 2
    sec_stat = next(s for s in cat_stats if s.category == "セキュリティ")
    assert sec_stat.total_attempts == 2
    assert sec_stat.correct_attempts == 0
    assert sec_stat.accuracy_rate == 0.0

    arch_stat = next(s for s in cat_stats if s.category == "アーキテクチャ")
    assert arch_stat.total_attempts == 1
    assert arch_stat.correct_attempts == 1
    assert arch_stat.accuracy_rate == 1.0

    # Overall stats
    overall = repo.get_overall_stats()
    assert overall.total_attempts == 3
    assert overall.correct_attempts == 1
    assert pytest.approx(overall.accuracy_rate, 0.01) == 0.3333
    assert overall.distinct_questions_attempted == 2
    assert overall.total_sessions == 2

    # Weak question stats (Q2 should be rank 1 with 2 incorrect)
    weak_stats = repo.get_weak_question_stats(limit=5)
    assert len(weak_stats) == 2
    assert weak_stats[0].question_id == "Q2"
    assert weak_stats[0].incorrect_count == 2
    assert weak_stats[0].latest_is_correct is False


def test_empty_database_handling(temp_db_repo: SQLitePracticeHistoryRepository):
    repo = temp_db_repo

    # No attempts yet
    attempts = repo.get_attempts()
    assert attempts == []

    attempted_ids = repo.get_attempted_question_ids()
    assert attempted_ids == set()

    latest_map = repo.get_latest_attempt_per_question()
    assert latest_map == {}

    cat_stats = repo.get_category_stats()
    assert cat_stats == []

    overall = repo.get_overall_stats()
    assert overall.total_attempts == 0
    assert overall.accuracy_rate == 0.0

    weak = repo.get_weak_question_stats()
    assert weak == []


def test_connection_rollback_on_exception(temp_db_repo: SQLitePracticeHistoryRepository):
    repo = temp_db_repo

    # Simulate an error in transaction
    with pytest.raises(RuntimeError, match="Simulated failure"):
        with repo._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO practice_attempts (
                    id, session_id, question_id, exam_type, year, term,
                    question_number, category, user_choice, correct_answer,
                    is_correct, time_spent_seconds, answered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "fail-attempt",
                    None,
                    "Q1",
                    "SA",
                    2025,
                    "秋期",
                    1,
                    "Cat",
                    "ア",
                    "ア",
                    1,
                    1.0,
                    "2026-09-15T12:00:00Z",
                ),
            )
            raise RuntimeError("Simulated failure")

    # The attempt should be rolled back and not present in DB
    attempts = repo.get_attempts()
    assert len(attempts) == 0
