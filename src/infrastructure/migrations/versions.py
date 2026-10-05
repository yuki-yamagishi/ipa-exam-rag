"""Schema migration definitions for SQLite database."""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    """Individual database schema migration specification."""

    version: int
    description: str
    up: Callable[[sqlite3.Connection], None]


def _migrate_v1(conn: sqlite3.Connection) -> None:
    """V1: Initial baseline schema with practice_attempts table and 4 core indexes."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS practice_attempts (
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
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pa_question_id ON practice_attempts(question_id);"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pa_category ON practice_attempts(category);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pa_session_id ON practice_attempts(session_id);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pa_answered_at ON practice_attempts(answered_at);"
        )
    finally:
        cursor.close()


def _migrate_v2(conn: sqlite3.Connection) -> None:
    """V2: Add user_email column and index for multi-user isolation."""
    cursor = conn.cursor()
    try:
        # Verify existing columns to guarantee strict idempotency
        cursor.execute("PRAGMA table_info(practice_attempts);")
        columns = [row[1] for row in cursor.fetchall()]

        if "user_email" not in columns:
            cursor.execute(
                "ALTER TABLE practice_attempts ADD COLUMN user_email TEXT NOT NULL DEFAULT '';"
            )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pa_user_email ON practice_attempts(user_email);"
        )
    finally:
        cursor.close()


def _migrate_v3(conn: sqlite3.Connection) -> None:
    """V3: Add dojo_sessions table and indexes for resumable practice sessions."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dojo_sessions (
                session_id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL DEFAULT '',
                mode TEXT NOT NULL,
                year INTEGER,
                category TEXT,
                question_count INTEGER NOT NULL,
                shuffle INTEGER NOT NULL,
                question_ids TEXT NOT NULL,
                current_index INTEGER NOT NULL DEFAULT 0,
                results_json TEXT NOT NULL DEFAULT '[]',
                is_completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ds_user_active ON dojo_sessions(user_email, is_completed, updated_at);"
        )
    finally:
        cursor.close()


# Ordered registry of all historical migrations
MIGRATIONS: list[Migration] = [
    Migration(
        version=1,
        description="Initial baseline schema (practice_attempts with 4 indexes)",
        up=_migrate_v1,
    ),
    Migration(
        version=2,
        description="Add user_email column and index for user isolation",
        up=_migrate_v2,
    ),
    Migration(
        version=3,
        description="Add dojo_sessions table for resumable practice sessions",
        up=_migrate_v3,
    ),
]
