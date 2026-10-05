"""Tests for SQLite schema migration mechanism (PRAGMA user_version) - Issue #007."""

import sqlite3
from pathlib import Path

import pytest

from src.domain.models import AnswerKey, PracticeAttempt
from src.infrastructure.history_repository import SQLitePracticeHistoryRepository
from src.infrastructure.migrations.migrator import SchemaMigrator
from src.infrastructure.migrations.versions import MIGRATIONS, Migration


def test_scenario_1_fresh_database_reaches_latest_version():
    """シナリオ 1: 新規データベースの初期構築と最新バージョン到達 (正常系・新規作成)"""
    conn = sqlite3.connect(":memory:")
    migrator = SchemaMigrator()

    # Initial state
    assert migrator.get_current_version(conn) == 0

    # Apply all migrations
    applied = migrator.apply_all(conn)
    assert applied == len(MIGRATIONS)
    assert migrator.get_current_version(conn) == len(MIGRATIONS)

    # Check table existence and columns
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(practice_attempts);")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    assert "id" in columns
    assert "question_id" in columns
    assert "user_email" in columns
    assert columns["user_email"] == "TEXT"

    # Check indexes (4 from V1 + 1 from V2 = 5 total)
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='practice_attempts';"
    )
    indexes = {row[0] for row in cursor.fetchall()}
    assert "idx_pa_question_id" in indexes
    assert "idx_pa_category" in indexes
    assert "idx_pa_session_id" in indexes
    assert "idx_pa_answered_at" in indexes
    assert "idx_pa_user_email" in indexes

    conn.close()


def test_scenario_2_existing_v0_production_database_migration(tmp_path: Path):
    """シナリオ 2: 実稼働既存データベース (user_version == 0 かつデータ保持) からの完全自動昇格 (正常系・本番移行)"""
    db_file = tmp_path / "v0_legacy.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    # Emulate legacy V0 schema (created by CREATE TABLE IF NOT EXISTS without version header)
    cursor.execute(
        """
        CREATE TABLE practice_attempts (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            question_id TEXT NOT NULL,
            exam_type TEXT NOT NULL,
            year INTEGER NOT NULL,
            term TEXT NOT NULL,
            question_number INTEGER NOT NULL,
            category TEXT NOT NULL,
            user_choice TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            time_spent_seconds REAL NOT NULL,
            answered_at TEXT NOT NULL
        );
        """
    )
    # Insert 10 legacy attempt records
    for i in range(1, 11):
        cursor.execute(
            """
            INSERT INTO practice_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"legacy-attempt-{i}",
                "session-v0",
                f"2025-SA-AM2-Q{i:02d}",
                "SA",
                2025,
                "秋期",
                i,
                "システムアーキテクチャ設計",
                "ア",
                "ア",
                1,
                15.0,
                f"2026-09-15T10:{i:02d}:00Z",
            ),
        )
    conn.commit()

    # Pre-condition: user_version is 0 and 10 records exist
    migrator = SchemaMigrator()
    assert migrator.get_current_version(conn) == 0

    cursor.execute("SELECT COUNT(*) FROM practice_attempts;")
    assert cursor.fetchone()[0] == 10

    # Action: Run migration
    applied = migrator.apply_all(conn)
    assert applied == len(MIGRATIONS)
    assert migrator.get_current_version(conn) == len(MIGRATIONS)

    # Post-condition: All 10 records preserved, user_email defaults to empty string
    cursor.execute("SELECT id, user_email FROM practice_attempts ORDER BY question_number ASC;")
    rows = cursor.fetchall()
    assert len(rows) == 10
    for row in rows:
        assert row[1] == ""

    conn.close()


def test_scenario_3_v1_database_incremental_upgrade():
    """シナリオ 3: V1 相当（user_version == 1）からの差分自動マイグレーション (正常系・スキーマ進化)"""
    conn = sqlite3.connect(":memory:")
    migrator = SchemaMigrator()

    # Manually execute V1 and set version to 1
    MIGRATIONS[0].up(conn)
    migrator.set_version(conn, 1)
    conn.commit()

    assert migrator.get_current_version(conn) == 1

    # Insert a record under V1
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO practice_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "att-v1",
            "s-1",
            "2025-SA-AM2-Q01",
            "SA",
            2025,
            "秋期",
            1,
            "Tech",
            "ア",
            "ア",
            1,
            5.0,
            "2026-09-17T00:00:00Z",
        ),
    )
    conn.commit()

    # Apply remaining migrations (should apply all remaining migrations after V1)
    applied = migrator.apply_all(conn)
    assert applied == len(MIGRATIONS) - 1
    assert migrator.get_current_version(conn) == len(MIGRATIONS)

    # Verify column added and record preserved
    cursor.execute("SELECT id, user_email FROM practice_attempts WHERE id = 'att-v1';")
    row = cursor.fetchone()
    assert row[0] == "att-v1"
    assert row[1] == ""

    conn.close()


def test_scenario_4_idempotent_when_already_at_latest_version():
    """シナリオ 4: 最新バージョン到達済みデータベースに対する冪等性 (正常系・冪等性)"""
    conn = sqlite3.connect(":memory:")
    migrator = SchemaMigrator()

    # First run
    applied_first = migrator.apply_all(conn)
    assert applied_first == len(MIGRATIONS)
    assert migrator.get_current_version(conn) == len(MIGRATIONS)

    # Second run (idempotent)
    applied_second = migrator.apply_all(conn)
    assert applied_second == 0
    assert migrator.get_current_version(conn) == len(MIGRATIONS)

    conn.close()


def test_scenario_5_rollback_on_migration_failure():
    """シナリオ 5: マイグレーション障害時の完全ロールバックと整合性保全 (異常系・原子性)"""
    conn = sqlite3.connect(":memory:")

    # Define a faulty migration
    def _faulty_migration(c: sqlite3.Connection) -> None:
        cur = c.cursor()
        try:
            cur.execute("CREATE TABLE temp_valid_table (id INT);")
            cur.execute("INVALID SQL SYNTAX HERE;")
        finally:
            cur.close()

    custom_migrations = [
        MIGRATIONS[0],  # V1 succeeds
        Migration(version=2, description="Faulty step", up=_faulty_migration),
    ]
    migrator = SchemaMigrator(migrations=custom_migrations)

    # Execution should raise exception on V2
    with pytest.raises(sqlite3.OperationalError):
        migrator.apply_all(conn)

    # Verify atomic rollback of V2: version must remain at 1, and temp_valid_table must not exist
    assert migrator.get_current_version(conn) == 1

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='temp_valid_table';")
    assert cursor.fetchone() is None

    conn.close()


def test_scenario_6_sqlite_repository_transparent_integration(tmp_path: Path):
    """シナリオ 6: SQLitePracticeHistoryRepository との完全透過的統合 (正常系・リポジトリ結合)"""
    db_file = tmp_path / "integrated_history.db"

    # Instantiate repository (triggers auto-migration under the hood)
    repo = SQLitePracticeHistoryRepository(db_path=db_file)

    # Record attempt with user_email
    attempt = PracticeAttempt(
        id="attempt-user-test",
        session_id="session-user-1",
        question_id="2025-SA-AM2-Q01",
        exam_type="SA",
        year=2025,
        term="秋期",
        question_number=1,
        category="システムアーキテクチャ設計",
        user_choice=AnswerKey.A,
        correct_answer=AnswerKey.A,
        is_correct=True,
        time_spent_seconds=8.5,
        user_email="test.student@example.com",
    )
    repo.record_attempt(attempt)

    # Fetch attempts
    attempts = repo.get_attempts()
    assert len(attempts) == 1
    fetched = attempts[0]
    assert fetched.id == "attempt-user-test"
    assert fetched.user_email == "test.student@example.com"

    # Fetch latest attempt
    latest_map = repo.get_latest_attempt_per_question()
    assert "2025-SA-AM2-Q01" in latest_map
    assert latest_map["2025-SA-AM2-Q01"].user_email == "test.student@example.com"
