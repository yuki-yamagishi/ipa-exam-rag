"""Schema migration runner executing incremental migrations via PRAGMA user_version."""

import logging
import sqlite3

from src.infrastructure.migrations.versions import MIGRATIONS, Migration

logger = logging.getLogger(__name__)


class SchemaMigrator:
    """Manages database schema state, version inspection, and incremental updates."""

    def __init__(self, migrations: list[Migration] | None = None):
        self.migrations: list[Migration] = sorted(
            migrations if migrations is not None else MIGRATIONS,
            key=lambda m: m.version,
        )

    @staticmethod
    def get_current_version(conn: sqlite3.Connection) -> int:
        """Read current schema version from SQLite header."""
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA user_version;")
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        finally:
            cursor.close()

    @staticmethod
    def set_version(conn: sqlite3.Connection, version: int) -> None:
        """Write schema version into SQLite header."""
        cursor = conn.cursor()
        try:
            cursor.execute(f"PRAGMA user_version = {int(version)};")
        finally:
            cursor.close()

    def apply_all(self, conn: sqlite3.Connection) -> int:
        """Apply all pending migrations in ascending order within individual transactions.

        Returns:
            Number of migrations applied.
        """
        current_version = self.get_current_version(conn)
        pending = [m for m in self.migrations if m.version > current_version]

        if not pending:
            logger.debug("Database schema is up to date at version %d.", current_version)
            return 0

        logger.info(
            "Current schema version is %d. Found %d pending migration(s).",
            current_version,
            len(pending),
        )

        applied_count = 0
        original_isolation = conn.isolation_level
        conn.isolation_level = None  # Manual explicit transaction control to allow DDL rollbacks

        try:
            for m in pending:
                logger.info("Applying migration V%d: %s...", m.version, m.description)
                conn.execute("BEGIN;")
                try:
                    # Execute migration step and version bump atomically
                    m.up(conn)
                    self.set_version(conn, m.version)
                    conn.execute("COMMIT;")
                    applied_count += 1
                    logger.info("Successfully applied migration V%d.", m.version)
                except Exception as e:
                    conn.execute("ROLLBACK;")
                    logger.error("Migration V%d failed: %s. Rolled back changes.", m.version, e)
                    raise
        finally:
            conn.isolation_level = original_isolation

        final_version = self.get_current_version(conn)
        logger.info("Database schema successfully updated to version %d.", final_version)
        return applied_count
