"""
Schema migration runner for the Vociferous SQLite database.

Design rules:
- MIGRATIONS is an ordered list of (description, fn) pairs, one entry per version.
- Versions are 1-indexed: MIGRATIONS[0] = v1, MIGRATIONS[1] = v2, etc.
- Append new entries to add a migration; never edit or reorder existing ones.
- Each migration function receives an open sqlite3.Connection.
  It should call conn.execute() / conn.executescript() as needed but NOT commit —
  the runner commits after each successful migration.
- A failed migration raises; the version counter is NOT advanced, leaving the
  database in a consistent pre-migration state.
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Migration functions
# ---------------------------------------------------------------------------


def _v1_baseline(conn: sqlite3.Connection) -> None:  # noqa: ARG001
    """v1 — Baseline schema (projects, transcripts, transcript_variants, indexes).

    The three core tables and their indexes are created by TranscriptDB._CREATE_SQL
    before migrations run, so this function is intentionally a no-op. It exists
    solely to record v1 in schema_version for all new and upgraded installs.
    """


def _v2_add_fts5(conn: sqlite3.Connection) -> None:
    """v2 — Add FTS5 virtual table and sync triggers for full-text search.

    Creates a content-table FTS5 index backed by the ``transcripts`` table and
    three triggers (INSERT / DELETE / UPDATE) to keep the index in sync. Existing
    rows are backfilled so old databases are immediately searchable.
    """
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
            raw_text,
            normalized_text,
            content='transcripts',
            content_rowid='id'
        )
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS transcripts_ai AFTER INSERT ON transcripts BEGIN
            INSERT INTO transcripts_fts(rowid, raw_text, normalized_text)
            VALUES (new.id, new.raw_text, new.normalized_text);
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS transcripts_ad AFTER DELETE ON transcripts BEGIN
            INSERT INTO transcripts_fts(transcripts_fts, rowid, raw_text, normalized_text)
            VALUES ('delete', old.id, old.raw_text, old.normalized_text);
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS transcripts_au AFTER UPDATE ON transcripts BEGIN
            INSERT INTO transcripts_fts(transcripts_fts, rowid, raw_text, normalized_text)
            VALUES ('delete', old.id, old.raw_text, old.normalized_text);
            INSERT INTO transcripts_fts(rowid, raw_text, normalized_text)
            VALUES (new.id, new.raw_text, new.normalized_text);
        END
        """
    )
    # Backfill existing rows into the FTS index
    conn.execute(
        """
        INSERT INTO transcripts_fts(rowid, raw_text, normalized_text)
        SELECT id, raw_text, normalized_text FROM transcripts
        """
    )


# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------

#: Ordered list of (human-readable description, migration function) pairs.
#: Append here to add future migrations; do not edit existing entries.
MIGRATIONS: list[tuple[str, object]] = [
    ("v1 baseline — projects / transcripts / transcript_variants", _v1_baseline),
    ("v2 FTS5 full-text search index and sync triggers", _v2_add_fts5),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply all pending schema migrations in version order.

    Reads the current version from ``schema_version``, skips already-applied
    migrations, and runs each pending one inside its own transaction. The
    version counter is updated immediately after each successful migration so
    that a partial run leaves the database at the last successfully applied
    version rather than rolling everything back.

    Raises on the first migration failure, leaving ``schema_version`` at the
    last successfully applied version.
    """
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    current: int = row[0] if row else 0
    target: int = len(MIGRATIONS)

    if current >= target:
        logger.debug("DB schema up to date at v%d", current)
        return

    logger.info(
        "DB schema: at v%d, target v%d — applying %d migration(s)",
        current,
        target,
        target - current,
    )

    for idx, (description, migrate_fn) in enumerate(MIGRATIONS, start=1):
        if idx <= current:
            continue

        try:
            migrate_fn(conn)  # type: ignore[operator]

            # Record the new version (insert on first migration, update thereafter)
            if current == 0 and not conn.execute("SELECT 1 FROM schema_version").fetchone():
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (idx,))
            else:
                conn.execute("UPDATE schema_version SET version = ?", (idx,))

            conn.commit()
            current = idx
            logger.info("DB migration applied: %s", description)

        except Exception:
            logger.exception("DB migration FAILED at %s (v%d) — aborting", description, idx)
            raise
