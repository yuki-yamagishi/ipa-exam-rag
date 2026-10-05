"""SQLite implementation of practice history repository."""

import json
import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from src.domain.interfaces import IPracticeHistoryRepository
from src.domain.models import (
    AnswerKey,
    CategoryStat,
    DojoMode,
    DojoSessionState,
    OverallStat,
    PracticeAttempt,
    WeakQuestionStat,
)
from src.infrastructure.config import settings
from src.infrastructure.migrations.migrator import SchemaMigrator

logger = logging.getLogger(__name__)


class SQLitePracticeHistoryRepository(IPracticeHistoryRepository):
    """SQLite-backed repository for student practice attempts and performance analytics."""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path) if db_path is not None else settings.sqlite_db_path
        self._is_memory = self.db_path == ":memory:"

        if self._is_memory:
            self._mem_conn: sqlite3.Connection | None = sqlite3.connect(
                ":memory:", check_same_thread=False
            )
            self._mem_conn.row_factory = sqlite3.Row
        else:
            self._mem_conn = None
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for SQLite connections ensuring clean closure and explicit rollback."""
        if self._is_memory and self._mem_conn is not None:
            try:
                yield self._mem_conn
                self._mem_conn.commit()
            except Exception:
                self._mem_conn.rollback()
                raise
        else:
            conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def close(self) -> None:
        """Explicitly close persistent connections (e.g. in-memory)."""
        if self._mem_conn is not None:
            self._mem_conn.close()
            self._mem_conn = None

    def _init_db(self) -> None:
        """Initialize database schema and apply pending migrations."""
        if self._is_memory:
            conn = self._mem_conn
            assert conn is not None
            migrator = SchemaMigrator()
            migrator.apply_all(conn)
        else:
            conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                migrator = SchemaMigrator()
                migrator.apply_all(conn)
            finally:
                conn.close()

    def record_attempt(self, attempt: PracticeAttempt) -> None:
        """Persist a single practice attempt."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO practice_attempts (
                    id, session_id, question_id, exam_type, year, term,
                    question_number, category, user_choice, correct_answer,
                    is_correct, time_spent_seconds, user_email, answered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.id,
                    attempt.session_id,
                    attempt.question_id,
                    attempt.exam_type,
                    attempt.year,
                    attempt.term,
                    attempt.question_number,
                    attempt.category,
                    attempt.user_choice.value,
                    attempt.correct_answer.value,
                    1 if attempt.is_correct else 0,
                    attempt.time_spent_seconds,
                    attempt.user_email,
                    attempt.answered_at,
                ),
            )

    def get_attempts(
        self, question_id: str | None = None, limit: int = 100
    ) -> list[PracticeAttempt]:
        """Fetch attempt history, optionally filtered by question ID."""
        with self._connection() as conn:
            cursor = conn.cursor()
            if question_id:
                cursor.execute(
                    """
                    SELECT id, session_id, question_id, exam_type, year, term,
                           question_number, category, user_choice, correct_answer,
                           is_correct, time_spent_seconds, user_email, answered_at
                    FROM practice_attempts
                    WHERE question_id = ?
                    ORDER BY answered_at DESC
                    LIMIT ?
                    """,
                    (question_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, session_id, question_id, exam_type, year, term,
                           question_number, category, user_choice, correct_answer,
                           is_correct, time_spent_seconds, user_email, answered_at
                    FROM practice_attempts
                    ORDER BY answered_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            rows = cursor.fetchall()
            return [
                PracticeAttempt(
                    id=row["id"],
                    session_id=row["session_id"],
                    question_id=row["question_id"],
                    exam_type=row["exam_type"],
                    year=row["year"],
                    term=row["term"],
                    question_number=row["question_number"],
                    category=row["category"],
                    user_choice=AnswerKey(row["user_choice"]),
                    correct_answer=AnswerKey(row["correct_answer"]),
                    is_correct=bool(row["is_correct"]),
                    time_spent_seconds=row["time_spent_seconds"],
                    user_email=row["user_email"] if "user_email" in row.keys() else "",
                    answered_at=row["answered_at"],
                )
                for row in rows
            ]

    def get_attempted_question_ids(self) -> set[str]:
        """Return the set of unique question IDs that have been attempted."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT question_id FROM practice_attempts")
            rows = cursor.fetchall()
            return {row["question_id"] for row in rows}

    def get_latest_attempt_per_question(self) -> dict[str, PracticeAttempt]:
        """Return a mapping of question_id to the most recent PracticeAttempt."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                WITH Ranked AS (
                    SELECT *,
                           ROW_NUMBER() OVER(
                                PARTITION BY question_id
                                ORDER BY answered_at DESC, rowid DESC
                           ) as rn
                    FROM practice_attempts
                )
                SELECT id, session_id, question_id, exam_type, year, term,
                       question_number, category, user_choice, correct_answer,
                       is_correct, time_spent_seconds, user_email, answered_at
                FROM Ranked
                WHERE rn = 1
                """
            )
            rows = cursor.fetchall()
            result: dict[str, PracticeAttempt] = {}
            for row in rows:
                result[row["question_id"]] = PracticeAttempt(
                    id=row["id"],
                    session_id=row["session_id"],
                    question_id=row["question_id"],
                    exam_type=row["exam_type"],
                    year=row["year"],
                    term=row["term"],
                    question_number=row["question_number"],
                    category=row["category"],
                    user_choice=AnswerKey(row["user_choice"]),
                    correct_answer=AnswerKey(row["correct_answer"]),
                    is_correct=bool(row["is_correct"]),
                    time_spent_seconds=row["time_spent_seconds"],
                    user_email=row["user_email"] if "user_email" in row.keys() else "",
                    answered_at=row["answered_at"],
                )
            return result

    def get_category_stats(self) -> list[CategoryStat]:
        """Return aggregated statistics grouped by question category."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT category,
                       COUNT(*) as total_attempts,
                       SUM(is_correct) as correct_attempts
                FROM practice_attempts
                GROUP BY category
                ORDER BY total_attempts DESC
                """
            )
            rows = cursor.fetchall()
            stats: list[CategoryStat] = []
            for row in rows:
                total = row["total_attempts"]
                correct = row["correct_attempts"] or 0
                accuracy = round(correct / total, 4) if total > 0 else 0.0
                stats.append(
                    CategoryStat(
                        category=row["category"],
                        total_attempts=total,
                        correct_attempts=correct,
                        accuracy_rate=accuracy,
                    )
                )
            return stats

    def get_overall_stats(self) -> OverallStat:
        """Return overall aggregate statistics across all attempts."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as total_attempts,
                       COALESCE(SUM(is_correct), 0) as correct_attempts,
                       COUNT(DISTINCT question_id) as distinct_questions,
                       COUNT(DISTINCT session_id) as total_sessions
                FROM practice_attempts
                """
            )
            row = cursor.fetchone()
            if not row or row["total_attempts"] == 0:
                return OverallStat()

            total = row["total_attempts"]
            correct = row["correct_attempts"]
            accuracy = round(correct / total, 4) if total > 0 else 0.0

            return OverallStat(
                total_attempts=total,
                correct_attempts=correct,
                accuracy_rate=accuracy,
                distinct_questions_attempted=row["distinct_questions"],
                total_sessions=row["total_sessions"],
            )

    def get_weak_question_stats(self, limit: int = 5) -> list[WeakQuestionStat]:
        """Return questions with highest incorrect counts or latest incorrect attempts."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                WITH Latest AS (
                    SELECT question_id, is_correct,
                           ROW_NUMBER() OVER(
                               PARTITION BY question_id
                               ORDER BY answered_at DESC, rowid DESC
                           ) as rn
                    FROM practice_attempts
                ),
                Agg AS (
                    SELECT question_id, question_number, category,
                           COUNT(*) as total_attempts,
                           SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END) as incorrect_count
                    FROM practice_attempts
                    GROUP BY question_id, question_number, category
                )
                SELECT Agg.question_id, Agg.question_number, Agg.category,
                       Agg.total_attempts, Agg.incorrect_count,
                       Latest.is_correct as latest_is_correct
                FROM Agg
                JOIN Latest ON Agg.question_id = Latest.question_id AND Latest.rn = 1
                ORDER BY Latest.is_correct ASC, Agg.incorrect_count DESC, Agg.total_attempts DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                WeakQuestionStat(
                    question_id=row["question_id"],
                    question_number=row["question_number"],
                    category=row["category"],
                    question_text="",  # To be enriched by application service if needed
                    total_attempts=row["total_attempts"],
                    incorrect_count=row["incorrect_count"],
                    latest_is_correct=bool(row["latest_is_correct"]),
                )
                for row in rows
            ]

    def clear_all_attempts(self) -> None:
        """Clear all practice attempt records (for testing or reset)."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM practice_attempts")

    def clear_all(self) -> None:
        """Clear all practice attempts and dojo sessions."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM practice_attempts")
            cursor.execute("DELETE FROM dojo_sessions")

    def save_session_state(self, session: DojoSessionState) -> None:
        """Persist or update an active dojo practice session."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO dojo_sessions (
                    session_id, user_email, mode, year, category, question_count,
                    shuffle, question_ids, current_index, results_json,
                    is_completed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    current_index=excluded.current_index,
                    results_json=excluded.results_json,
                    is_completed=excluded.is_completed,
                    updated_at=excluded.updated_at
                """,
                (
                    session.session_id,
                    session.user_email,
                    session.mode.value if hasattr(session.mode, "value") else str(session.mode),
                    session.year,
                    session.category,
                    session.question_count,
                    1 if session.shuffle else 0,
                    json.dumps(session.question_ids, ensure_ascii=False),
                    session.current_index,
                    json.dumps(session.results, ensure_ascii=False),
                    1 if session.is_completed else 0,
                    session.created_at,
                    session.updated_at,
                ),
            )

    def get_active_session(self, user_email: str = "") -> DojoSessionState | None:
        """Fetch the most recent uncompleted dojo session for a user if exists."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT session_id, user_email, mode, year, category, question_count,
                       shuffle, question_ids, current_index, results_json,
                       is_completed, created_at, updated_at
                FROM dojo_sessions
                WHERE user_email = ? AND is_completed = 0
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (user_email,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return DojoSessionState(
                session_id=row["session_id"],
                user_email=row["user_email"],
                mode=DojoMode(row["mode"]),
                year=row["year"],
                category=row["category"],
                question_count=row["question_count"],
                shuffle=bool(row["shuffle"]),
                question_ids=json.loads(row["question_ids"]),
                current_index=row["current_index"],
                results=json.loads(row["results_json"]),
                is_completed=bool(row["is_completed"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def get_session_by_id(self, session_id: str) -> DojoSessionState | None:
        """Fetch a specific dojo session by session ID regardless of completion status."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT session_id, user_email, mode, year, category, question_count,
                       shuffle, question_ids, current_index, results_json,
                       is_completed, created_at, updated_at
                FROM dojo_sessions
                WHERE session_id = ?
                LIMIT 1
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return DojoSessionState(
                session_id=row["session_id"],
                user_email=row["user_email"],
                mode=DojoMode(row["mode"]),
                year=row["year"],
                category=row["category"],
                question_count=row["question_count"],
                shuffle=bool(row["shuffle"]),
                question_ids=json.loads(row["question_ids"]),
                current_index=row["current_index"],
                results=json.loads(row["results_json"]),
                is_completed=bool(row["is_completed"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def mark_session_completed(self, session_id: str) -> None:
        """Mark a dojo session as completed."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE dojo_sessions
                SET is_completed = 1, updated_at = ?
                WHERE session_id = ?
                """,
                (datetime.now(UTC).isoformat(), session_id),
            )

    def delete_session(self, session_id: str) -> None:
        """Permanently remove or abandon a dojo session."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dojo_sessions WHERE session_id = ?", (session_id,))
