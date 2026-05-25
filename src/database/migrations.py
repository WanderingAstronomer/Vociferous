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


def _transcripts_timestamp_has_unique_constraint(conn: sqlite3.Connection) -> bool:
    for row in conn.execute("PRAGMA index_list(transcripts)").fetchall():
        index_name = row[1]
        is_unique = bool(row[2])
        if not is_unique:
            continue
        columns = [info[2] for info in conn.execute(f"PRAGMA index_info({index_name})").fetchall()]
        if columns == ["timestamp"]:
            return True
    return False


def _v12_timestamp_not_unique(conn: sqlite3.Connection) -> None:
    """v12 ΓÇö Rebuild transcripts so timestamp is indexed but not unique."""
    if not _transcripts_timestamp_has_unique_constraint(conn):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON transcripts(timestamp)")
        logger.info("v12 migration: transcript timestamp already non-unique")
        return

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS transcripts_ai;
        DROP TRIGGER IF EXISTS transcripts_ad;
        DROP TRIGGER IF EXISTS transcripts_au;

        ALTER TABLE transcripts RENAME TO transcripts_old;

        CREATE TABLE transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            normalized_text TEXT NOT NULL,
            display_name TEXT,
            duration_ms INTEGER DEFAULT 0,
            speech_duration_ms INTEGER DEFAULT 0,
            transcription_time_ms INTEGER DEFAULT 0,
            refinement_time_ms INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
            include_in_analytics INTEGER NOT NULL DEFAULT 1,
            has_audio_cached INTEGER NOT NULL DEFAULT 0,
            is_protected INTEGER NOT NULL DEFAULT 0,
            compound_root_id INTEGER REFERENCES transcripts(id) ON DELETE CASCADE,
            compound_order INTEGER
        );

        INSERT INTO transcripts (
            id, timestamp, raw_text, normalized_text, display_name,
            duration_ms, speech_duration_ms, transcription_time_ms, refinement_time_ms,
            created_at, include_in_analytics, has_audio_cached, is_protected,
            compound_root_id, compound_order
        )
        SELECT
            id, timestamp, raw_text, normalized_text, display_name,
            duration_ms, speech_duration_ms, transcription_time_ms, refinement_time_ms,
            created_at, include_in_analytics, has_audio_cached, is_protected,
            compound_root_id, compound_order
        FROM transcripts_old;

                DROP TABLE transcripts_old;

                ALTER TABLE transcript_tags RENAME TO transcript_tags_old;

                CREATE TABLE transcript_tags (
                        transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
                        tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                        UNIQUE(transcript_id, tag_id)
                );

                INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id)
                SELECT transcript_id, tag_id FROM transcript_tags_old
                WHERE transcript_id IN (SELECT id FROM transcripts)
                    AND tag_id IN (SELECT id FROM tags);

                DROP TABLE transcript_tags_old;

        CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON transcripts(timestamp);
        CREATE INDEX IF NOT EXISTS idx_transcripts_compound_root ON transcripts(compound_root_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_transcripts_compound_member_order
            ON transcripts(compound_root_id, compound_order);
        CREATE INDEX IF NOT EXISTS idx_transcript_tags_transcript ON transcript_tags(transcript_id);
        CREATE INDEX IF NOT EXISTS idx_transcript_tags_tag ON transcript_tags(tag_id);

        CREATE TRIGGER IF NOT EXISTS transcripts_ai AFTER INSERT ON transcripts BEGIN
            INSERT INTO transcripts_fts(rowid, raw_text, normalized_text)
            VALUES (new.id, new.raw_text, new.normalized_text);
        END;
        CREATE TRIGGER IF NOT EXISTS transcripts_ad AFTER DELETE ON transcripts BEGIN
            INSERT INTO transcripts_fts(transcripts_fts, rowid, raw_text, normalized_text)
            VALUES ('delete', old.id, old.raw_text, old.normalized_text);
        END;
        CREATE TRIGGER IF NOT EXISTS transcripts_au AFTER UPDATE ON transcripts BEGIN
            INSERT INTO transcripts_fts(transcripts_fts, rowid, raw_text, normalized_text)
            VALUES ('delete', old.id, old.raw_text, old.normalized_text);
            INSERT INTO transcripts_fts(rowid, raw_text, normalized_text)
            VALUES (new.id, new.raw_text, new.normalized_text);
        END;
        """
    )
    conn.execute("PRAGMA foreign_keys=ON")
    logger.info("v12 migration: transcript timestamp uniqueness removed")


_CLEAN_VERBATIM_FAST = """\
Text repair. Fix grammar, spelling, and punctuation.

- Do not change words unless they are transcription errors.
- Break into paragraphs to avoid long walls of text.
- Do not use any Markdown formatting (no asterisks, no bullets, no headers).
- Output only the corrected text.
"""

_CLEAN_VERBATIM_DEEP = """\
You are a verbatim transcript editor. Your job is to clean up speech-to-text output while preserving the speaker's exact colloquialisms and voice.

- Fix all punctuation, capitalization, and obvious transcription errors (e.g., homophones).
- Insert paragraph breaks for readability when the topic subtly shifts.
- Do not rephrase sentences, summarize, or "improve" the text structure.
- Do not use Markdown formatting.
- Output only the repaired text. No conversational filler or explanations.
"""

_MARKDOWN_REWRITE_FAST = """\
Rewrite the text into clean Markdown.

- Fix all grammar and punctuation.
- Break into logical paragraphs.
- Use **bold** for key terms and *italic* for emphasis.
- Use bullet points if a list is spoken.
- Do NOT use headers (#).
- Output only the Markdown text.
"""

_MARKDOWN_REWRITE_DEEP = """\
Rewrite the transcription into polished, well-structured Markdown.

- Create readable paragraphs with clear breaks.
- Use `##` for distinct major topics (never use `#`).
- Use **bold** for key concepts and *italic* for titles or introduced terms.
- Use bulleted or numbered lists where enumerations naturally exist in the text.
- Preserve the speaker's original voice, meaning, and intent. Remove only verbal filler (ums, ahs) and false starts.
- Output only the final Markdown. No conversational filler or explanations.
"""


def _v13_seed_markdown_refinement_prompts(conn: sqlite3.Connection) -> None:
    """v13 — Replace the generic shipped prompt with two Markdown prompt templates.

    Shipped prompts are protected prompt-library records, not user transcript
    data. They intentionally carry blank timestamps and analytics exclusion so
    every count/date/stat path has to work hard to accidentally include them.
    """
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS transcripts_ai;
        DROP TRIGGER IF EXISTS transcripts_ad;
        DROP TRIGGER IF EXISTS transcripts_au;
        DROP TABLE IF EXISTS transcripts_fts;
        """
    )

    existing_tag = conn.execute("SELECT id FROM tags WHERE name = 'Prompt' AND is_system = 1").fetchone()
    if existing_tag:
        prompt_tag_id = existing_tag[0]
    else:
        cur = conn.execute("INSERT INTO tags (name, color, is_system) VALUES ('Prompt', NULL, 1)")
        prompt_tag_id = cur.lastrowid

    shipped_prompts = (
        ("Clean Verbatim (Fast)", _CLEAN_VERBATIM_FAST),
        ("Clean Verbatim (Deep)", _CLEAN_VERBATIM_DEEP),
        ("Markdown Rewrite (Fast)", _MARKDOWN_REWRITE_FAST),
        ("Markdown Rewrite (Deep)", _MARKDOWN_REWRITE_DEEP),
    )

    old_default = conn.execute(
        "SELECT id FROM transcripts WHERE display_name = 'Default Refinement Prompt' AND is_protected = 1"
    ).fetchone()
    small_existing = conn.execute(
        "SELECT id FROM transcripts WHERE display_name = ? AND is_protected = 1",
        (shipped_prompts[0][0],),
    ).fetchone()

    if old_default and not small_existing:
        conn.execute(
            """UPDATE transcripts
               SET timestamp = '', created_at = '', raw_text = ?, normalized_text = ?, display_name = ?,
                   duration_ms = 0, speech_duration_ms = 0, transcription_time_ms = 0,
                   refinement_time_ms = 0, include_in_analytics = 0,
                   has_audio_cached = 0, is_protected = 1
               WHERE id = ?""",
            (shipped_prompts[0][1], shipped_prompts[0][1], shipped_prompts[0][0], old_default[0]),
        )
        conn.execute(
            "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
            (old_default[0], prompt_tag_id),
        )

    for title, prompt_text in shipped_prompts:
        existing = conn.execute(
            "SELECT id FROM transcripts WHERE display_name = ? AND is_protected = 1",
            (title,),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE transcripts
                   SET timestamp = '', created_at = '', include_in_analytics = 0,
                       duration_ms = 0, speech_duration_ms = 0, transcription_time_ms = 0,
                       refinement_time_ms = 0, has_audio_cached = 0, is_protected = 1
                   WHERE id = ?""",
                (existing[0],),
            )
            conn.execute(
                "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
                (existing[0], prompt_tag_id),
            )
            continue

        cur = conn.execute(
            """INSERT INTO transcripts
               (timestamp, raw_text, normalized_text, display_name,
                duration_ms, speech_duration_ms, transcription_time_ms,
                refinement_time_ms, created_at, include_in_analytics,
                has_audio_cached, is_protected)
               VALUES ('', ?, ?, ?, 0, 0, 0, 0, '', 0, 0, 1)""",
            (prompt_text, prompt_text, title),
        )
        conn.execute(
            "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
            (cur.lastrowid, prompt_tag_id),
        )

    _v2_add_fts5(conn)
    logger.info("v13 migration: shipped Markdown refinement prompts seeded outside analytics")


def _v14_audio_vault(conn: sqlite3.Connection) -> None:
    """v14 — Add durable audio vault tables for crash-recoverable recordings."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS recording_sessions (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            finalized_at TEXT,
            sample_rate INTEGER NOT NULL,
            channels INTEGER NOT NULL,
            sample_width_bytes INTEGER NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            frame_count INTEGER NOT NULL DEFAULT 0,
            byte_count INTEGER NOT NULL DEFAULT 0,
            last_durable_chunk INTEGER NOT NULL DEFAULT -1,
            audio_path TEXT NOT NULL,
            encrypted INTEGER NOT NULL DEFAULT 0,
            encryption_key_id TEXT,
            transcript_id INTEGER REFERENCES transcripts(id) ON DELETE SET NULL,
            failure_reason TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_recording_sessions_status ON recording_sessions(status);
        CREATE INDEX IF NOT EXISTS idx_recording_sessions_transcript ON recording_sessions(transcript_id);

        CREATE TABLE IF NOT EXISTS recording_chunks (
            recording_id TEXT NOT NULL REFERENCES recording_sessions(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            start_frame INTEGER NOT NULL,
            frame_count INTEGER NOT NULL,
            byte_offset INTEGER NOT NULL,
            byte_count INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            written_at TEXT NOT NULL,
            fsynced_at TEXT NOT NULL,
            PRIMARY KEY (recording_id, chunk_index)
        );

        CREATE TABLE IF NOT EXISTS audio_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recording_id TEXT REFERENCES recording_sessions(id) ON DELETE SET NULL,
            transcript_id INTEGER REFERENCES transcripts(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            path TEXT NOT NULL,
            duration_ms INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL,
            encrypted INTEGER NOT NULL DEFAULT 0,
            pinned INTEGER NOT NULL DEFAULT 0,
            retain_until TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_audio_assets_recording ON audio_assets(recording_id);
        CREATE INDEX IF NOT EXISTS idx_audio_assets_transcript ON audio_assets(transcript_id);
        CREATE INDEX IF NOT EXISTS idx_audio_assets_role ON audio_assets(role);
        """
    )
    logger.info("v14 migration: durable audio vault tables ensured")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _table_has_foreign_key_target(conn: sqlite3.Connection, table_name: str, target_table: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return any(row[2] == target_table for row in conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall())


def _v15_repair_audio_vault_transcript_foreign_keys(conn: sqlite3.Connection) -> None:
    """v15 — Repair audio vault FKs retargeted to transcripts_old during v12.

    TranscriptDB creates the current baseline schema before applying migrations. On old databases at v11 or earlier,
    that means v14-era audio vault tables can already exist before v12 rebuilds transcripts. SQLite then rewrites their
    transcript_id foreign keys from transcripts to the temporary transcripts_old table. After v12 drops transcripts_old,
    inserting a recording session fails with "no such table: main.transcripts_old". Absolutely delightful.
    """
    stale_tables = [
        table_name
        for table_name in ("recording_sessions", "audio_assets")
        if _table_has_foreign_key_target(conn, table_name, "transcripts_old")
    ]
    if not stale_tables:
        _v14_audio_vault(conn)
        logger.info("v15 migration: audio vault transcript foreign keys already valid")
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(
            """
            DROP TABLE IF EXISTS recording_sessions_new;
            DROP TABLE IF EXISTS audio_assets_new;

            CREATE TABLE recording_sessions_new (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                finalized_at TEXT,
                sample_rate INTEGER NOT NULL,
                channels INTEGER NOT NULL,
                sample_width_bytes INTEGER NOT NULL,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                frame_count INTEGER NOT NULL DEFAULT 0,
                byte_count INTEGER NOT NULL DEFAULT 0,
                last_durable_chunk INTEGER NOT NULL DEFAULT -1,
                audio_path TEXT NOT NULL,
                encrypted INTEGER NOT NULL DEFAULT 0,
                encryption_key_id TEXT,
                transcript_id INTEGER REFERENCES transcripts(id) ON DELETE SET NULL,
                failure_reason TEXT
            );

            INSERT INTO recording_sessions_new (
                id, status, started_at, updated_at, finalized_at, sample_rate, channels,
                sample_width_bytes, duration_ms, frame_count, byte_count, last_durable_chunk,
                audio_path, encrypted, encryption_key_id, transcript_id, failure_reason
            )
            SELECT
                id, status, started_at, updated_at, finalized_at, sample_rate, channels,
                sample_width_bytes, duration_ms, frame_count, byte_count, last_durable_chunk,
                audio_path, encrypted, encryption_key_id,
                CASE
                    WHEN transcript_id IS NULL THEN NULL
                    WHEN EXISTS (SELECT 1 FROM transcripts WHERE transcripts.id = recording_sessions.transcript_id)
                        THEN transcript_id
                    ELSE NULL
                END,
                failure_reason
            FROM recording_sessions;

            DROP TABLE recording_sessions;
            ALTER TABLE recording_sessions_new RENAME TO recording_sessions;

            CREATE INDEX IF NOT EXISTS idx_recording_sessions_status ON recording_sessions(status);
            CREATE INDEX IF NOT EXISTS idx_recording_sessions_transcript ON recording_sessions(transcript_id);

            CREATE TABLE audio_assets_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recording_id TEXT REFERENCES recording_sessions(id) ON DELETE SET NULL,
                transcript_id INTEGER REFERENCES transcripts(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                path TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                encrypted INTEGER NOT NULL DEFAULT 0,
                pinned INTEGER NOT NULL DEFAULT 0,
                retain_until TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
            );

            INSERT INTO audio_assets_new (
                id, recording_id, transcript_id, role, path, duration_ms, size_bytes,
                encrypted, pinned, retain_until, created_at
            )
            SELECT
                id,
                CASE
                    WHEN recording_id IS NULL THEN NULL
                    WHEN EXISTS (SELECT 1 FROM recording_sessions WHERE recording_sessions.id = audio_assets.recording_id)
                        THEN recording_id
                    ELSE NULL
                END,
                CASE
                    WHEN transcript_id IS NULL THEN NULL
                    WHEN EXISTS (SELECT 1 FROM transcripts WHERE transcripts.id = audio_assets.transcript_id)
                        THEN transcript_id
                    ELSE NULL
                END,
                role, path, duration_ms, size_bytes, encrypted, pinned, retain_until, created_at
            FROM audio_assets;

            DROP TABLE audio_assets;
            ALTER TABLE audio_assets_new RENAME TO audio_assets;

            CREATE INDEX IF NOT EXISTS idx_audio_assets_recording ON audio_assets(recording_id);
            CREATE INDEX IF NOT EXISTS idx_audio_assets_transcript ON audio_assets(transcript_id);
            CREATE INDEX IF NOT EXISTS idx_audio_assets_role ON audio_assets(role);
            """
        )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    logger.info(
        "v15 migration: rebuilt audio vault tables to repair stale transcript foreign keys (%s)",
        ", ".join(stale_tables),
    )


def _v16_processing_provenance(conn: sqlite3.Connection) -> None:
    """v16 — Persist ASR/SLM provider, model, and prompt provenance on transcripts."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transcripts)").fetchall()}
    additions = (
        ("transcription_provider", "TEXT NOT NULL DEFAULT ''"),
        ("transcription_model_id", "TEXT NOT NULL DEFAULT ''"),
        ("transcription_prompt_text", "TEXT NOT NULL DEFAULT ''"),
        ("transcription_prompt_chars", "INTEGER NOT NULL DEFAULT 0"),
        ("transcription_prompt_words", "INTEGER NOT NULL DEFAULT 0"),
        ("refinement_provider", "TEXT NOT NULL DEFAULT ''"),
        ("refinement_model_id", "TEXT NOT NULL DEFAULT ''"),
        ("refinement_prompt_text", "TEXT NOT NULL DEFAULT ''"),
        ("refinement_prompt_chars", "INTEGER NOT NULL DEFAULT 0"),
        ("refinement_prompt_words", "INTEGER NOT NULL DEFAULT 0"),
    )
    for column_name, column_sql in additions:
        if column_name not in cols:
            conn.execute(f"ALTER TABLE transcripts ADD COLUMN {column_name} {column_sql}")
    logger.info("v16 migration: transcript processing provenance columns added")


def _v17_processing_runtime_context(conn: sqlite3.Connection) -> None:
    """v17 — Persist runtime context, refinement token counts, and separate re-transcription metadata."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transcripts)").fetchall()}
    additions = (
        ("transcription_resolved_device", "TEXT NOT NULL DEFAULT ''"),
        ("transcription_compute_type", "TEXT NOT NULL DEFAULT ''"),
        ("transcription_cpu_threads", "INTEGER NOT NULL DEFAULT 0"),
        ("retranscription_count", "INTEGER NOT NULL DEFAULT 0"),
        ("last_retranscription_at", "TEXT NOT NULL DEFAULT ''"),
        ("last_retranscription_time_ms", "INTEGER NOT NULL DEFAULT 0"),
        ("last_retranscription_provider", "TEXT NOT NULL DEFAULT ''"),
        ("last_retranscription_model_id", "TEXT NOT NULL DEFAULT ''"),
        ("last_retranscription_resolved_device", "TEXT NOT NULL DEFAULT ''"),
        ("last_retranscription_compute_type", "TEXT NOT NULL DEFAULT ''"),
        ("last_retranscription_cpu_threads", "INTEGER NOT NULL DEFAULT 0"),
        ("last_retranscription_prompt_text", "TEXT NOT NULL DEFAULT ''"),
        ("last_retranscription_prompt_chars", "INTEGER NOT NULL DEFAULT 0"),
        ("last_retranscription_prompt_words", "INTEGER NOT NULL DEFAULT 0"),
        ("refinement_resolved_device", "TEXT NOT NULL DEFAULT ''"),
        ("refinement_compute_type", "TEXT NOT NULL DEFAULT ''"),
        ("refinement_cpu_threads", "INTEGER NOT NULL DEFAULT 0"),
        ("refinement_gpu_layers", "INTEGER NOT NULL DEFAULT 0"),
        ("refinement_use_thinking", "INTEGER NOT NULL DEFAULT 0"),
        ("refinement_prompt_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("refinement_completion_tokens", "INTEGER NOT NULL DEFAULT 0"),
        ("refinement_total_tokens", "INTEGER NOT NULL DEFAULT 0"),
    )
    for column_name, column_sql in additions:
        if column_name not in cols:
            conn.execute(f"ALTER TABLE transcripts ADD COLUMN {column_name} {column_sql}")
    logger.info("v17 migration: runtime context, refinement token counts, and retranscription columns added")


def _v18_prompt_grid(conn: sqlite3.Connection) -> None:
    """v18 — Delete legacy v13 Prompts and install the 4-prompt grid."""
    # Wipe the legacy v13 prompts if they exist (clean removal)
    conn.execute(
        "DELETE FROM transcripts WHERE is_protected = 1 AND display_name IN ('Small Model Markdown Refinement Prompt', 'Large Model Structured Markdown Prompt')"
    )
    # The v13 migration might not have seeded the new ones for existing users because they already ran v13.
    # We just explicitly call logic the new v13 script uses to seed the new ones.
    _v13_seed_markdown_refinement_prompts(conn)
    logger.info("v18 migration: legacy prompts wiped, new prompt grid seeded")


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
    ("v12 timestamp not unique — preserve rapid transcript inserts", _v12_timestamp_not_unique),
    ("v13 shipped Markdown refinement prompts — prompt-library records only", _v13_seed_markdown_refinement_prompts),
    ("v14 audio vault — durable recording manifests and assets", _v14_audio_vault),
    (
        "v15 audio vault FK repair — remove stale transcripts_old references",
        _v15_repair_audio_vault_transcript_foreign_keys,
    ),
    ("v16 processing provenance — provider/model/prompt metadata on transcripts", _v16_processing_provenance),
    (
        "v17 processing runtime context — resolved device, refinement tokens, and retranscription metadata",
        _v17_processing_runtime_context,
    ),
    ("v18 prompt grid — clean verbatim vs markdown rewrites", _v18_prompt_grid),
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
