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


def _v3_projects_to_tags(conn: sqlite3.Connection) -> None:
    """v3 — Create tags + transcript_tags tables; migrate existing projects to tags.

    Flattens the hierarchical project tree into a flat tag set. Each project
    (including sub-projects) becomes a tag. Transcripts that were assigned to
    a project get the corresponding tag added via the junction table.

    The projects table and transcripts.project_id column are left in place
    (not dropped) for backward compatibility with older code paths, but new
    code exclusively uses tags.
    """
    # Create tags table (if not already created by _CREATE_SQL on fresh DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            color TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
        )
        """
    )
    # Create junction table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transcript_tags (
            transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            UNIQUE(transcript_id, tag_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_transcript_tags_transcript ON transcript_tags(transcript_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_transcript_tags_tag ON transcript_tags(tag_id)")

    # Migrate existing projects → tags (only if projects table exists — fresh installs
    # after v4 schema cleanup won't have it)
    has_projects = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'").fetchone()
    if not has_projects:
        logger.info("v3 migration: no projects table (fresh install) — tags tables created, nothing to migrate")
        return

    projects = conn.execute("SELECT id, name, color FROM projects ORDER BY id").fetchall()
    project_to_tag: dict[int, int] = {}

    for p in projects:
        cur = conn.execute(
            "INSERT INTO tags (name, color) VALUES (?, ?)",
            (p["name"], p["color"]),
        )
        project_to_tag[p["id"]] = cur.lastrowid  # type: ignore[assignment]

    # Migrate transcript → project assignments to transcript_tags junction rows
    assigned = conn.execute("SELECT id, project_id FROM transcripts WHERE project_id IS NOT NULL").fetchall()

    for row in assigned:
        tag_id = project_to_tag.get(row["project_id"])
        if tag_id is not None:
            conn.execute(
                "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
                (row["id"], tag_id),
            )

    logger.info(
        "v3 migration: converted %d projects → tags, migrated %d assignments",
        len(projects),
        len(assigned),
    )


def _v4_drop_projects_and_variants(conn: sqlite3.Connection) -> None:
    """v4 — Remove legacy projects table and transcript_variants system.

    For existing databases:
      1. Copies current variant text into normalized_text (data preservation).
      2. Drops transcript_variants table and projects table.
      3. Removes project_id and current_variant_id columns from transcripts.

    Fresh installs (post-v4 _CREATE_SQL) won't have these objects, so every
    step guards with IF EXISTS / column-existence checks.
    """
    # Phase 1: Preserve variant data — copy current variant text to normalized_text
    has_variants = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='transcript_variants'"
    ).fetchone()
    if has_variants:
        conn.execute(
            """UPDATE transcripts SET normalized_text = (
                   SELECT tv.text FROM transcript_variants tv
                   WHERE tv.id = transcripts.current_variant_id
               )
               WHERE current_variant_id IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM transcript_variants tv
                   WHERE tv.id = transcripts.current_variant_id
               )"""
        )
        logger.info("v4 migration: variant text preserved into normalized_text")

    # Phase 2: Drop indexes first (must precede column drops)
    conn.execute("DROP INDEX IF EXISTS idx_transcripts_project")
    conn.execute("DROP INDEX IF EXISTS idx_variants_transcript")

    # Phase 3: Drop dependent tables.
    # Commit any open implicit transaction before touching PRAGMA foreign_keys —
    # SQLite silently ignores FK pragma changes issued mid-transaction (Python 3.6+
    # no longer auto-commits before DDL, so the Phase 1 UPDATE leaves one open).
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE IF EXISTS transcript_variants")
    conn.execute("DROP TABLE IF EXISTS projects")
    conn.execute("PRAGMA foreign_keys = ON")

    # Phase 4: Remove vestigial columns (SQLite 3.35+, guaranteed by Python 3.12+)
    # Column drops require no active FK constraints on the column, so disable temporarily.
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transcripts)").fetchall()}
    if "project_id" in cols:
        conn.execute("ALTER TABLE transcripts DROP COLUMN project_id")
    if "current_variant_id" in cols:
        conn.execute("ALTER TABLE transcripts DROP COLUMN current_variant_id")

    logger.info("v4 migration: dropped projects table, transcript_variants table, and vestigial columns")


def _v5_system_tags(conn: sqlite3.Connection) -> None:
    """v5 — Add is_system flag to tags; seed the 'Refined' system tag.

    is_system=1 marks tags that are managed by the application and cannot be
    edited or deleted by the user. Fresh installs get the column from
    _CREATE_SQL; existing databases get it via ALTER TABLE here.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(tags)").fetchall()}
    if "is_system" not in cols:
        conn.execute("ALTER TABLE tags ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0")

    existing = conn.execute("SELECT id FROM tags WHERE name = 'Refined' AND is_system = 1").fetchone()
    if not existing:
        conn.execute("INSERT INTO tags (name, color, is_system) VALUES ('Refined', NULL, 1)")

    logger.info("v5 migration: is_system column ensured + Refined system tag seeded")


#: Ordered list of (human-readable description, migration function) pairs.
#: Append here to add future migrations; do not edit existing entries.
MIGRATIONS: list[tuple[str, object]] = [
    ("v1 baseline — projects / transcripts / transcript_variants", _v1_baseline),
    ("v2 FTS5 full-text search index and sync triggers", _v2_add_fts5),
    ("v3 tags — flat tag system replacing hierarchical projects", _v3_projects_to_tags),
    ("v4 drop projects + variants — simplified transcript model", _v4_drop_projects_and_variants),
    ("v5 system tags — is_system column + Refined tag seeded", _v5_system_tags),
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
