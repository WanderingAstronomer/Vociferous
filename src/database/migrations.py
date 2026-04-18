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
        project_to_tag[p["id"]] = cur.lastrowid

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


def _v7_compound_tag(conn: sqlite3.Connection) -> None:
    """v7 — Seed the 'Compound' system tag for transcript continuation/append.

    Transcripts that have had additional recordings appended to them receive
    this tag automatically. Fresh installs get it immediately; existing databases
    get it here alongside the already-seeded 'Refined' tag.
    """
    existing = conn.execute("SELECT id FROM tags WHERE name = 'Compound' AND is_system = 1").fetchone()
    if not existing:
        conn.execute("INSERT INTO tags (name, color, is_system) VALUES ('Compound', NULL, 1)")
    logger.info("v7 migration: Compound system tag ensured")


def _v6_analytics_inclusion(conn: sqlite3.Connection) -> None:
    """v6 — Add include_in_analytics flag to transcripts.

    Defaults to 1 (included) for all existing transcripts. Users can
    set this per-transcript in EditView to exclude junk/test recordings
    from WPM averages and other personal analytics.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transcripts)").fetchall()}
    if "include_in_analytics" not in cols:
        conn.execute("ALTER TABLE transcripts ADD COLUMN include_in_analytics INTEGER NOT NULL DEFAULT 1")
    logger.info("v6 migration: include_in_analytics column ensured on transcripts")


def _v8_audio_cache_flag(conn: sqlite3.Connection) -> None:
    """v8 — Add has_audio_cached flag to transcripts.

    Tracks whether a cached WAV file exists for a transcript, enabling
    the re-transcribe button in the UI. Defaults to 0 (no cached audio).
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transcripts)").fetchall()}
    if "has_audio_cached" not in cols:
        conn.execute("ALTER TABLE transcripts ADD COLUMN has_audio_cached INTEGER NOT NULL DEFAULT 0")
    logger.info("v8 migration: has_audio_cached column ensured on transcripts")


def _v9_prompt_system(conn: sqlite3.Connection) -> None:
    """v9 — Prompt tag, is_protected column, and default system prompt transcript.

    Adds the "Prompt" system tag (is_system=1) for tagging reusable instruction
    templates.  Adds an is_protected column to transcripts so the seeded default
    system prompt cannot be deleted.  Seeds the default refinement system prompt
    as a protected transcript tagged with the Prompt tag.
    """
    # 1. is_protected column on transcripts
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transcripts)").fetchall()}
    if "is_protected" not in cols:
        conn.execute("ALTER TABLE transcripts ADD COLUMN is_protected INTEGER NOT NULL DEFAULT 0")

    # 2. Seed "Prompt" system tag
    existing_tag = conn.execute("SELECT id FROM tags WHERE name = 'Prompt' AND is_system = 1").fetchone()
    if existing_tag:
        prompt_tag_id = existing_tag[0]
    else:
        cur = conn.execute("INSERT INTO tags (name, color, is_system) VALUES ('Prompt', NULL, 1)")
        prompt_tag_id = cur.lastrowid

    # 3. Seed default system prompt transcript (idempotent via display_name check)
    default_prompt_text = "You are a professional editor and proofreader."
    existing_prompt = conn.execute(
        "SELECT id FROM transcripts WHERE display_name = 'Default Refinement Prompt' AND is_protected = 1"
    ).fetchone()
    if not existing_prompt:
        ts = "1970-01-01T00:00:00.000"  # sentinel timestamp for seeded data
        cur = conn.execute(
            """INSERT INTO transcripts
               (timestamp, raw_text, normalized_text, display_name,
                duration_ms, speech_duration_ms, created_at,
                include_in_analytics, has_audio_cached, is_protected)
               VALUES (?, ?, ?, ?, 0, 0, ?, 0, 0, 1)""",
            (ts, default_prompt_text, default_prompt_text, "Default Refinement Prompt", ts),
        )
        prompt_transcript_id = cur.lastrowid
        # Tag the seeded transcript with the Prompt tag
        conn.execute(
            "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
            (prompt_transcript_id, prompt_tag_id),
        )

    logger.info("v9 migration: Prompt system tag + default system prompt transcript seeded")


def _v10_processing_timing(conn: sqlite3.Connection) -> None:
    """v10 — Add transcription_time_ms and refinement_time_ms to transcripts.

    Stores how long Whisper inference took (transcription) and how long
    SLM refinement took, enabling processing performance analytics.
    Both default to 0 for existing transcripts (no historical timing data).
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transcripts)").fetchall()}
    if "transcription_time_ms" not in cols:
        conn.execute("ALTER TABLE transcripts ADD COLUMN transcription_time_ms INTEGER DEFAULT 0")
    if "refinement_time_ms" not in cols:
        conn.execute("ALTER TABLE transcripts ADD COLUMN refinement_time_ms INTEGER DEFAULT 0")
    logger.info("v10 migration: transcription_time_ms + refinement_time_ms columns added")


def _v11_compound_membership(conn: sqlite3.Connection) -> None:
    """v11 — Add lightweight compound membership metadata to transcripts."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transcripts)").fetchall()}
    if "compound_root_id" not in cols:
        conn.execute(
            "ALTER TABLE transcripts ADD COLUMN compound_root_id INTEGER REFERENCES transcripts(id) ON DELETE CASCADE"
        )
    if "compound_order" not in cols:
        conn.execute("ALTER TABLE transcripts ADD COLUMN compound_order INTEGER")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_compound_root ON transcripts(compound_root_id)")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_transcripts_compound_member_order ON transcripts(compound_root_id, compound_order)"
    )

    logger.info("v11 migration: compound membership columns ensured on transcripts")


#: Ordered list of (human-readable description, migration function) pairs.
#: Append here to add future migrations; do not edit existing entries.
MIGRATIONS: list[tuple[str, object]] = [
    ("v1 baseline — projects / transcripts / transcript_variants", _v1_baseline),
    ("v2 FTS5 full-text search index and sync triggers", _v2_add_fts5),
    ("v3 tags — flat tag system replacing hierarchical projects", _v3_projects_to_tags),
    ("v4 drop projects + variants — simplified transcript model", _v4_drop_projects_and_variants),
    ("v5 system tags — is_system column + Refined tag seeded", _v5_system_tags),
    ("v6 analytics inclusion flag — include_in_analytics column on transcripts", _v6_analytics_inclusion),
    ("v7 compound system tag — seed Compound tag for transcript continuation", _v7_compound_tag),
    ("v8 audio cache flag — has_audio_cached column on transcripts", _v8_audio_cache_flag),
    ("v9 prompt system — Prompt tag + is_protected column + default system prompt transcript", _v9_prompt_system),
    ("v10 processing timing — transcription_time_ms + refinement_time_ms columns", _v10_processing_timing),
    ("v11 compound membership — preserve non-destructive append members", _v11_compound_membership),
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
