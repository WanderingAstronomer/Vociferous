"""
Vociferous Database — Raw sqlite3 + dataclasses.

5 tables (tags, transcript_tags, transcripts, schema_version,
transcripts_fts), WAL mode.
Replaces SQLAlchemy ORM. Schema evolution is managed by
src/database/migrations.py.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

from src.core.resource_manager import ResourceManager
from src.database.models import AudioAsset, RecordingSessionRecord, Tag, Transcript, utc_now

logger = logging.getLogger(__name__)

# Re-exported for backwards compatibility — these now live in src.database.models.
__all__ = [
    "AudioAsset",
    "RecordingSessionRecord",
    "Tag",
    "Transcript",
    "TranscriptDB",
    "normalize_tag_filter_mode",
    "utc_now",
]

TAG_FILTER_MODE_ALIASES: dict[str, str] = {
    "any": "or",
    "all": "and",
    "or": "or",
    "and": "and",
    "not": "not",
    "nand": "nand",
    "xor": "xor",
}


def normalize_tag_filter_mode(tag_mode: str) -> str:
    """Normalize supported tag filter modes, preserving legacy any/all aliases."""
    normalized = TAG_FILTER_MODE_ALIASES.get(tag_mode.strip().lower())
    if normalized is None:
        raise ValueError("tag_mode must be one of: or, and, not, nand, xor")
    return normalized


# --- Database ---


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    display_name TEXT,
    duration_ms INTEGER DEFAULT 0,
    speech_duration_ms INTEGER DEFAULT 0,
    transcription_time_ms INTEGER DEFAULT 0,
    refinement_time_ms INTEGER DEFAULT 0,
    transcription_provider TEXT NOT NULL DEFAULT '',
    transcription_model_id TEXT NOT NULL DEFAULT '',
    transcription_resolved_device TEXT NOT NULL DEFAULT '',
    transcription_compute_type TEXT NOT NULL DEFAULT '',
    transcription_cpu_threads INTEGER NOT NULL DEFAULT 0,
    transcription_prompt_text TEXT NOT NULL DEFAULT '',
    transcription_prompt_chars INTEGER NOT NULL DEFAULT 0,
    transcription_prompt_words INTEGER NOT NULL DEFAULT 0,
    retranscription_count INTEGER NOT NULL DEFAULT 0,
    last_retranscription_at TEXT NOT NULL DEFAULT '',
    last_retranscription_time_ms INTEGER NOT NULL DEFAULT 0,
    last_retranscription_provider TEXT NOT NULL DEFAULT '',
    last_retranscription_model_id TEXT NOT NULL DEFAULT '',
    last_retranscription_resolved_device TEXT NOT NULL DEFAULT '',
    last_retranscription_compute_type TEXT NOT NULL DEFAULT '',
    last_retranscription_cpu_threads INTEGER NOT NULL DEFAULT 0,
    last_retranscription_prompt_text TEXT NOT NULL DEFAULT '',
    last_retranscription_prompt_chars INTEGER NOT NULL DEFAULT 0,
    last_retranscription_prompt_words INTEGER NOT NULL DEFAULT 0,
    refinement_provider TEXT NOT NULL DEFAULT '',
    refinement_model_id TEXT NOT NULL DEFAULT '',
    refinement_resolved_device TEXT NOT NULL DEFAULT '',
    refinement_compute_type TEXT NOT NULL DEFAULT '',
    refinement_cpu_threads INTEGER NOT NULL DEFAULT 0,
    refinement_gpu_layers INTEGER NOT NULL DEFAULT 0,
    refinement_use_thinking INTEGER NOT NULL DEFAULT 0,
    refinement_prompt_text TEXT NOT NULL DEFAULT '',
    refinement_prompt_chars INTEGER NOT NULL DEFAULT 0,
    refinement_prompt_words INTEGER NOT NULL DEFAULT 0,
    refinement_prompt_tokens INTEGER NOT NULL DEFAULT 0,
    refinement_completion_tokens INTEGER NOT NULL DEFAULT 0,
    refinement_total_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    include_in_analytics INTEGER NOT NULL DEFAULT 1,
    has_audio_cached INTEGER NOT NULL DEFAULT 0,
    is_protected INTEGER NOT NULL DEFAULT 0,
    compound_root_id INTEGER REFERENCES transcripts(id) ON DELETE CASCADE,
    compound_order INTEGER
);

CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON transcripts(timestamp);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    color TEXT,
    is_system INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE TABLE IF NOT EXISTS transcript_tags (
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    UNIQUE(transcript_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_transcript_tags_transcript ON transcript_tags(transcript_id);
CREATE INDEX IF NOT EXISTS idx_transcript_tags_tag ON transcript_tags(tag_id);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

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


class TranscriptDB:
    """
    Minimal sqlite3 database for transcript history.

    WAL mode for concurrent read access. All writes are serialized.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = ResourceManager.get_user_data_dir() / "vociferous.db"
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_CREATE_SQL)
        self._conn.commit()

        from src.database.migrations import run_migrations

        run_migrations(self._conn)
        row = self._conn.execute("SELECT MAX(timestamp) FROM transcripts").fetchone()
        self._last_timestamp = row[0] if row and row[0] else ""

    def close(self) -> None:
        self._conn.close()

    # --- Transcripts ---

    def add_transcript(
        self,
        raw_text: str,
        *,
        normalized_text: str | None = None,
        duration_ms: int = 0,
        speech_duration_ms: int = 0,
        transcription_time_ms: int = 0,
        transcription_provider: str = "",
        transcription_model_id: str = "",
        transcription_resolved_device: str = "",
        transcription_compute_type: str = "",
        transcription_cpu_threads: int = 0,
        transcription_prompt_text: str = "",
        transcription_prompt_chars: int = 0,
        transcription_prompt_words: int = 0,
        display_name: str | None = None,
        tag_ids: list[int] | None = None,
    ) -> Transcript:
        """Insert a new transcript. Returns the created transcript."""
        norm = normalized_text if normalized_text is not None else raw_text
        with self._write_lock, self._conn:
            ts = self._next_timestamp_locked()
            cur = self._conn.execute(
                """INSERT INTO transcripts
                   (timestamp, raw_text, normalized_text, display_name,
                    duration_ms, speech_duration_ms, transcription_time_ms,
                    transcription_provider, transcription_model_id,
                    transcription_resolved_device, transcription_compute_type,
                    transcription_cpu_threads,
                    transcription_prompt_text, transcription_prompt_chars,
                    transcription_prompt_words, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ts,
                    raw_text,
                    norm,
                    display_name,
                    duration_ms,
                    speech_duration_ms,
                    transcription_time_ms,
                    transcription_provider,
                    transcription_model_id,
                    transcription_resolved_device,
                    transcription_compute_type,
                    transcription_cpu_threads,
                    transcription_prompt_text,
                    transcription_prompt_chars,
                    transcription_prompt_words,
                    ts,
                ),
            )
            tid = cur.lastrowid
            assert tid is not None

            # Assign tags if provided
            tags: list[Tag] = []
            if tag_ids:
                for tag_id in tag_ids:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
                        (tid, tag_id),
                    )
                tags = self._get_tags_for_transcript(tid)

        return Transcript(
            id=tid,
            timestamp=ts,
            raw_text=raw_text,
            normalized_text=norm,
            display_name=display_name,
            duration_ms=duration_ms,
            speech_duration_ms=speech_duration_ms,
            transcription_time_ms=transcription_time_ms,
            transcription_provider=transcription_provider,
            transcription_model_id=transcription_model_id,
            transcription_resolved_device=transcription_resolved_device,
            transcription_compute_type=transcription_compute_type,
            transcription_cpu_threads=transcription_cpu_threads,
            transcription_prompt_text=transcription_prompt_text,
            transcription_prompt_chars=transcription_prompt_chars,
            transcription_prompt_words=transcription_prompt_words,
            created_at=ts,
            tags=tags,
        )

    def _next_timestamp_locked(self) -> str:
        candidate = utc_now()
        if candidate <= self._last_timestamp:
            previous = datetime.fromisoformat(self._last_timestamp)
            candidate = (previous + timedelta(microseconds=1)).isoformat()
        self._last_timestamp = candidate
        return candidate

    def get_transcript(self, transcript_id: int) -> Transcript | None:
        """Get a single transcript with its tags."""
        with self._write_lock:
            row = self._conn.execute(
                "SELECT * FROM transcripts WHERE id = ?",
                (transcript_id,),
            ).fetchone()
            if row is None:
                return None
            transcript = self._row_to_transcript(row)
            transcript.tags = self._get_tags_for_transcript(transcript_id)
        return transcript

    # Allowed sort columns (whitelist to prevent SQL injection)
    _SORT_COLUMNS = frozenset({"created_at", "duration_ms", "speech_duration_ms", "display_name", "words", "silence"})

    # Map virtual sort keys to SQL expressions
    _SORT_EXPRESSIONS: dict[str, str] = {
        "created_at": "t.created_at",
        "duration_ms": "t.duration_ms",
        "speech_duration_ms": "t.speech_duration_ms",
        "display_name": "t.display_name",
        "words": "(LENGTH(COALESCE(t.normalized_text, t.raw_text)) - LENGTH(REPLACE(COALESCE(t.normalized_text, t.raw_text), ' ', '')) + 1)",
        "silence": "(t.duration_ms - t.speech_duration_ms)",
    }

    def _paginate(
        self,
        count_sql: str,
        rows_sql: str,
        count_params: tuple = (),
        rows_params: tuple = (),
    ) -> tuple[int, list]:
        """Execute a count query and a paginated rows query, returning (total, rows)."""
        total: int = self._conn.execute(count_sql, count_params).fetchone()[0]
        rows: list = self._conn.execute(rows_sql, rows_params).fetchall()
        return total, rows

    @staticmethod
    def _append_text(existing: str, incoming: str) -> str:
        """Append incoming text with a blank-line separator when both sides exist."""
        if not existing:
            return incoming
        if not incoming:
            return existing
        return existing + "\n\n" + incoming

    def recent(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        tag_ids: list[int] | None = None,
        tag_mode: str = "any",
        include_compound_children: bool = False,
        include_protected: bool = False,
    ) -> tuple[list[Transcript], int]:
        """Get transcripts with pagination and sorting.

        Args:
            limit: Max results per page.
            offset: Number of results to skip.
            sort_by: Column to sort by (created_at, duration_ms, speech_duration_ms, display_name).
            sort_dir: "asc" or "desc".
            tag_ids: Filter to transcripts having these tags.
            tag_mode: "or"/"any", "and"/"all", "not", "nand", or "xor".

        Returns:
            Tuple of (transcripts, total_count).
        """
        mode = normalize_tag_filter_mode(tag_mode)
        selected_tag_ids = list(dict.fromkeys(tag_ids or []))
        col = sort_by if sort_by in self._SORT_COLUMNS else "created_at"
        expr = self._SORT_EXPRESSIONS[col]
        direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
        order_clause = f"ORDER BY {expr} {direction}"

        with self._write_lock:
            visibility_conditions: list[str] = []
            if not include_compound_children:
                visibility_conditions.append("t.compound_root_id IS NULL")
            if not include_protected:
                visibility_conditions.append("t.is_protected = 0")

            query_conditions = [*visibility_conditions]
            query_params: list[int] = []
            if selected_tag_ids:
                placeholders = ",".join("?" * len(selected_tag_ids))
                if mode == "or":
                    query_conditions.append(
                        f"t.id IN (SELECT transcript_id FROM transcript_tags WHERE tag_id IN ({placeholders}))"
                    )
                    query_params.extend(selected_tag_ids)
                elif mode == "and":
                    query_conditions.append(
                        f"""t.id IN (
                               SELECT transcript_id FROM transcript_tags
                               WHERE tag_id IN ({placeholders})
                               GROUP BY transcript_id
                               HAVING COUNT(DISTINCT tag_id) = ?
                           )"""
                    )
                    query_params.extend((*selected_tag_ids, len(selected_tag_ids)))
                elif mode == "not":
                    query_conditions.append(
                        f"""NOT EXISTS (
                               SELECT 1 FROM transcript_tags tt
                               WHERE tt.transcript_id = t.id
                                 AND tt.tag_id IN ({placeholders})
                           )"""
                    )
                    query_params.extend(selected_tag_ids)
                elif mode == "nand":
                    query_conditions.append(
                        f"""t.id NOT IN (
                               SELECT transcript_id FROM transcript_tags
                               WHERE tag_id IN ({placeholders})
                               GROUP BY transcript_id
                               HAVING COUNT(DISTINCT tag_id) = ?
                           )"""
                    )
                    query_params.extend((*selected_tag_ids, len(selected_tag_ids)))
                else:
                    query_conditions.append(
                        f"""t.id IN (
                               SELECT transcript_id FROM transcript_tags
                               WHERE tag_id IN ({placeholders})
                               GROUP BY transcript_id
                               HAVING COUNT(DISTINCT tag_id) = 1
                           )"""
                    )
                    query_params.extend(selected_tag_ids)

            where_clause = f"WHERE {' AND '.join(query_conditions)} " if query_conditions else ""
            total, rows = self._paginate(
                f"SELECT COUNT(*) FROM transcripts t {where_clause}",
                f"SELECT t.* FROM transcripts t {where_clause}{order_clause} LIMIT ? OFFSET ?",
                tuple(query_params),
                (*query_params, limit, offset),
            )
            transcripts = [self._row_to_transcript(r) for r in rows]
            self._enrich_transcripts_with_tags(transcripts)
        return transcripts, total

    def search(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        *,
        include_compound_children: bool = False,
        include_protected: bool = False,
    ) -> list[Transcript]:
        """Full-text search across transcript text using FTS5.

        An empty *query* returns the most-recent transcripts (same as
        ``recent(limit=limit)``). Multi-word queries are split on whitespace
        and each token is matched as a prefix, so ``"py prog"`` finds
        "Python programming".
        """
        if not query.strip():
            items, _ = self.recent(
                limit=limit,
                offset=offset,
                include_compound_children=include_compound_children,
                include_protected=include_protected,
            )
            return items
        tokens = query.split()
        # Wrap each token as an FTS5 phrase with prefix wildcard.
        # Inner double-quotes are escaped by doubling them per FTS5 syntax.
        fts_terms = " ".join(f'"{token.replace(chr(34), chr(34) * 2)}"*' for token in tokens)
        with self._write_lock:
            visibility_conditions: list[str] = []
            if not include_compound_children:
                visibility_conditions.append("t.compound_root_id IS NULL")
            if not include_protected:
                visibility_conditions.append("t.is_protected = 0")
            visibility = ""
            if visibility_conditions:
                visibility = "AND " + " AND ".join(visibility_conditions)
            rows = self._conn.execute(
                f"""SELECT t.*
                   FROM transcripts t
                   WHERE t.id IN (SELECT rowid FROM transcripts_fts WHERE transcripts_fts MATCH ?)
                   {visibility}
                   ORDER BY t.created_at DESC LIMIT ? OFFSET ?""",
                (fts_terms, limit, offset),
            ).fetchall()
            transcripts = [self._row_to_transcript(r) for r in rows]
            self._enrich_transcripts_with_tags(transcripts)
        return transcripts

    def search_count(
        self,
        query: str,
        *,
        include_compound_children: bool = False,
        include_protected: bool = False,
    ) -> int:
        """Return the total number of transcripts matching *query* (for pagination)."""
        if not query.strip():
            return self.transcript_count(
                include_compound_children=include_compound_children,
                include_protected=include_protected,
            )
        tokens = query.split()
        fts_terms = " ".join(f'"{t.replace(chr(34), chr(34) * 2)}"*' for t in tokens)
        with self._write_lock:
            visibility_conditions = ["t.id IN (SELECT rowid FROM transcripts_fts WHERE transcripts_fts MATCH ?)"]
            if not include_compound_children:
                visibility_conditions.append("t.compound_root_id IS NULL")
            if not include_protected:
                visibility_conditions.append("t.is_protected = 0")
            where = " AND ".join(visibility_conditions)
            row = self._conn.execute(
                f"SELECT COUNT(*) FROM transcripts t WHERE {where}",
                (fts_terms,),
            ).fetchone()
        return row[0] if row else 0

    def delete_transcript(self, transcript_id: int) -> bool:
        """Delete a transcript (tag junction rows CASCADE). Refuses to delete protected transcripts."""
        with self._write_lock:
            cur = self._conn.execute(
                "DELETE FROM transcripts WHERE id = ? AND is_protected = 0 AND compound_root_id IS NULL",
                (transcript_id,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def batch_delete_transcripts(self, transcript_ids: list[int]) -> int:
        """Delete multiple transcripts in a single transaction. Skips protected rows. Returns count deleted."""
        if not transcript_ids:
            return 0
        placeholders = ",".join("?" * len(transcript_ids))
        with self._write_lock:
            cur = self._conn.execute(
                f"DELETE FROM transcripts WHERE id IN ({placeholders}) AND is_protected = 0 AND compound_root_id IS NULL",
                transcript_ids,
            )
            self._conn.commit()
            return cur.rowcount

    def clear_all_transcripts(self) -> int:
        """Delete all non-protected transcripts. Returns count deleted."""
        with self._write_lock:
            # transcript_tags ON DELETE CASCADE handles junction table cleanup
            cur = self._conn.execute("DELETE FROM transcripts WHERE is_protected = 0")
            self._conn.commit()
            return cur.rowcount

    def update_normalized_text(self, transcript_id: int, text: str) -> None:
        """Update the normalized_text field (for edits)."""
        with self._write_lock:
            self._conn.execute(
                "UPDATE transcripts SET normalized_text = ? WHERE id = ?",
                (text, transcript_id),
            )
            self._conn.commit()

    def update_display_name(self, transcript_id: int, name: str) -> bool:
        """Set the display_name for a transcript. Returns True if row existed."""
        with self._write_lock:
            cur = self._conn.execute(
                "UPDATE transcripts SET display_name = ? WHERE id = ?",
                (name, transcript_id),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def update_refinement_time(self, transcript_id: int, refinement_time_ms: int) -> None:
        """Set the refinement_time_ms for a transcript (called after SLM inference completes)."""
        with self._write_lock:
            self._conn.execute(
                "UPDATE transcripts SET refinement_time_ms = ? WHERE id = ?",
                (refinement_time_ms, transcript_id),
            )
            self._conn.commit()

    def update_refinement_processing_context(
        self,
        transcript_id: int,
        *,
        refinement_time_ms: int,
        refinement_provider: str,
        refinement_model_id: str,
        refinement_resolved_device: str,
        refinement_compute_type: str,
        refinement_cpu_threads: int,
        refinement_gpu_layers: int,
        refinement_use_thinking: bool,
        refinement_prompt_text: str,
        refinement_prompt_chars: int,
        refinement_prompt_words: int,
        refinement_prompt_tokens: int,
        refinement_completion_tokens: int,
        refinement_total_tokens: int,
    ) -> None:
        """Persist refinement timing plus provider/model/prompt provenance."""
        with self._write_lock:
            self._conn.execute(
                """UPDATE transcripts
                   SET refinement_time_ms = ?,
                       refinement_provider = ?,
                       refinement_model_id = ?,
                       refinement_resolved_device = ?,
                       refinement_compute_type = ?,
                       refinement_cpu_threads = ?,
                       refinement_gpu_layers = ?,
                       refinement_use_thinking = ?,
                       refinement_prompt_text = ?,
                       refinement_prompt_chars = ?,
                       refinement_prompt_words = ?,
                       refinement_prompt_tokens = ?,
                       refinement_completion_tokens = ?,
                       refinement_total_tokens = ?
                   WHERE id = ?""",
                (
                    refinement_time_ms,
                    refinement_provider,
                    refinement_model_id,
                    refinement_resolved_device,
                    refinement_compute_type,
                    refinement_cpu_threads,
                    refinement_gpu_layers,
                    int(refinement_use_thinking),
                    refinement_prompt_text,
                    refinement_prompt_chars,
                    refinement_prompt_words,
                    refinement_prompt_tokens,
                    refinement_completion_tokens,
                    refinement_total_tokens,
                    transcript_id,
                ),
            )
            self._conn.commit()

    def update_retranscription_processing_context(
        self,
        transcript_id: int,
        *,
        normalized_text: str,
        retranscription_time_ms: int,
        retranscription_provider: str,
        retranscription_model_id: str,
        retranscription_resolved_device: str,
        retranscription_compute_type: str,
        retranscription_cpu_threads: int,
        retranscription_prompt_text: str,
        retranscription_prompt_chars: int,
        retranscription_prompt_words: int,
    ) -> None:
        """Persist the latest re-transcription result without overwriting original transcription provenance."""
        retr_timestamp = utc_now()
        with self._write_lock:
            self._conn.execute(
                """UPDATE transcripts
                   SET normalized_text = ?,
                       retranscription_count = retranscription_count + 1,
                       last_retranscription_at = ?,
                       last_retranscription_time_ms = ?,
                       last_retranscription_provider = ?,
                       last_retranscription_model_id = ?,
                       last_retranscription_resolved_device = ?,
                       last_retranscription_compute_type = ?,
                       last_retranscription_cpu_threads = ?,
                       last_retranscription_prompt_text = ?,
                       last_retranscription_prompt_chars = ?,
                       last_retranscription_prompt_words = ?
                   WHERE id = ?""",
                (
                    normalized_text,
                    retr_timestamp,
                    retranscription_time_ms,
                    retranscription_provider,
                    retranscription_model_id,
                    retranscription_resolved_device,
                    retranscription_compute_type,
                    retranscription_cpu_threads,
                    retranscription_prompt_text,
                    retranscription_prompt_chars,
                    retranscription_prompt_words,
                    transcript_id,
                ),
            )
            self._conn.commit()

    # --- Tags ---

    def add_tag(self, name: str, *, color: str | None = None, is_system: bool = False) -> Tag:
        """Create a new tag."""
        ts = utc_now()
        with self._write_lock:
            cur = self._conn.execute(
                "INSERT INTO tags (name, color, is_system, created_at) VALUES (?, ?, ?, ?)",
                (name, color, int(is_system), ts),
            )
            self._conn.commit()
            return Tag(id=cur.lastrowid, name=name, color=color, is_system=is_system, created_at=ts)

    def get_tags(self) -> list[Tag]:
        """List all tags ordered by name."""
        with self._write_lock:
            rows = self._conn.execute("SELECT * FROM tags ORDER BY name").fetchall()
        return [
            Tag(
                id=r["id"], name=r["name"], color=r["color"], is_system=bool(r["is_system"]), created_at=r["created_at"]
            )
            for r in rows
        ]

    def get_tag(self, tag_id: int) -> Tag | None:
        """Fetch a single tag by ID."""
        with self._write_lock:
            row = self._conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
        if row is None:
            return None
        return Tag(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            is_system=bool(row["is_system"]),
            created_at=row["created_at"],
        )

    def update_tag(
        self,
        tag_id: int,
        *,
        name: str | None = None,
        color: str | None = None,
    ) -> Tag | None:
        """Update a tag's name and/or color. System tags cannot be modified."""
        existing = self.get_tag(tag_id)
        if existing is None or existing.is_system:
            return None
        updates: list[str] = []
        params: list[str | int | None] = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if color is not None:
            updates.append("color = ?")
            params.append(color)
        if not updates:
            return existing
        params.append(tag_id)
        with self._write_lock:
            self._conn.execute(
                f"UPDATE tags SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            self._conn.commit()
        return self.get_tag(tag_id)

    def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag. System tags cannot be deleted. Junction rows are cascade-deleted."""
        existing = self.get_tag(tag_id)
        if existing is None or existing.is_system:
            return False
        with self._write_lock:
            cur = self._conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # System tags that are auto-managed by the engine and must never be
    # stripped by a user-driven assign_tags call.
    _AUTO_MANAGED_SYSTEM_TAGS = ("Refined", "Compound")

    def assign_tags(self, transcript_id: int, tag_ids: list[int]) -> list[Tag]:
        """Set the exact user-tag set for a transcript.

        Preserves auto-managed system tags (Refined, Compound) that are
        applied by the engine.  User-assignable system tags (e.g. Prompt)
        are treated like normal tags and CAN be toggled via this method.
        """
        with self._write_lock:
            # Keep only the auto-managed system tags intact; everything else
            # (user tags AND user-assignable system tags like Prompt) is
            # replaced with the caller-supplied list.
            self._conn.execute(
                """DELETE FROM transcript_tags WHERE transcript_id = ?
                   AND tag_id NOT IN (
                       SELECT id FROM tags WHERE is_system = 1
                       AND name IN ('Refined', 'Compound')
                   )""",
                (transcript_id,),
            )
            for tag_id in tag_ids:
                self._conn.execute(
                    "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
                    (transcript_id, tag_id),
                )
            self._conn.commit()
            return self._get_tags_for_transcript(transcript_id)

    def add_tag_to_transcript(self, transcript_id: int, tag_id: int) -> None:
        """Add a single tag to a transcript (additive)."""
        with self._write_lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
                (transcript_id, tag_id),
            )
            self._conn.commit()

    def remove_tag_from_transcript(self, transcript_id: int, tag_id: int) -> None:
        """Remove a single tag from a transcript."""
        with self._write_lock:
            self._conn.execute(
                "DELETE FROM transcript_tags WHERE transcript_id = ? AND tag_id = ?",
                (transcript_id, tag_id),
            )
            self._conn.commit()

    def batch_toggle_tag(self, transcript_ids: list[int], tag_id: int, *, add: bool) -> None:
        """Add or remove a single tag from multiple transcripts in one transaction."""
        if not transcript_ids:
            return
        with self._write_lock:
            if add:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
                    [(tid, tag_id) for tid in transcript_ids],
                )
            else:
                self._conn.executemany(
                    "DELETE FROM transcript_tags WHERE transcript_id = ? AND tag_id = ?",
                    [(tid, tag_id) for tid in transcript_ids],
                )
            self._conn.commit()

    def _get_system_tag_id(self, tag_name: str) -> int | None:
        """Look up a system tag ID by name. Caller must hold _write_lock."""
        row = self._conn.execute(
            "SELECT id FROM tags WHERE name = ? AND is_system = 1",
            (tag_name,),
        ).fetchone()
        return row["id"] if row is not None else None

    def add_system_tag_to_transcript(self, transcript_id: int, tag_name: str) -> None:
        """Add a system tag (looked up by name) to a transcript. No-op if tag not found."""
        with self._write_lock:
            tag_id = self._get_system_tag_id(tag_name)
            if tag_id is None:
                return
            self._conn.execute(
                "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
                (transcript_id, tag_id),
            )
            self._conn.commit()

    def remove_system_tag_from_transcript(self, transcript_id: int, tag_name: str) -> None:
        """Remove a system tag (looked up by name) from a transcript. No-op if tag not found."""
        with self._write_lock:
            tag_id = self._get_system_tag_id(tag_name)
            if tag_id is None:
                return
            self._conn.execute(
                "DELETE FROM transcript_tags WHERE transcript_id = ? AND tag_id = ?",
                (transcript_id, tag_id),
            )
            self._conn.commit()

    def get_ids_with_system_tag(self, tag_name: str, ids: tuple[int, ...]) -> set[int]:
        """Return the subset of transcript IDs that already carry the named system tag."""
        if not ids:
            return set()
        placeholders = ",".join("?" * len(ids))
        with self._write_lock:
            rows = self._conn.execute(
                f"""SELECT tt.transcript_id FROM transcript_tags tt
                    JOIN tags t ON t.id = tt.tag_id
                    WHERE t.name = ? AND t.is_system = 1
                      AND tt.transcript_id IN ({placeholders})""",
                (tag_name, *ids),
            ).fetchall()
        return {row["transcript_id"] for row in rows}

    def _enrich_transcripts_with_tags(self, transcripts: list[Transcript]) -> None:
        """Batch-load and attach tags to a list of transcripts. Caller must hold _write_lock."""
        transcript_ids = [t.id for t in transcripts if t.id is not None]
        if not transcript_ids:
            return
        tags_by_transcript = self._get_tags_for_transcripts(transcript_ids)
        for transcript in transcripts:
            if transcript.id is not None:
                transcript.tags = tags_by_transcript.get(transcript.id, [])

    def _get_tags_for_transcript(self, transcript_id: int) -> list[Tag]:
        """Fetch all tags for a transcript. Caller must hold _write_lock."""
        rows = self._conn.execute(
            """SELECT t.* FROM tags t
               INNER JOIN transcript_tags tt ON t.id = tt.tag_id
               WHERE tt.transcript_id = ?
               ORDER BY t.name""",
            (transcript_id,),
        ).fetchall()
        return [
            Tag(
                id=r["id"], name=r["name"], color=r["color"], is_system=bool(r["is_system"]), created_at=r["created_at"]
            )
            for r in rows
        ]

    def _get_tags_for_transcripts(self, transcript_ids: list[int]) -> dict[int, list[Tag]]:
        """Fetch tags for multiple transcripts in one query. Caller must hold _write_lock."""
        if not transcript_ids:
            return {}

        placeholders = ",".join("?" * len(transcript_ids))
        rows = self._conn.execute(
            f"""SELECT tt.transcript_id, t.id, t.name, t.color, t.is_system, t.created_at
                FROM transcript_tags tt
                INNER JOIN tags t ON t.id = tt.tag_id
                WHERE tt.transcript_id IN ({placeholders})
                ORDER BY tt.transcript_id, t.name""",
            transcript_ids,
        ).fetchall()

        by_transcript: dict[int, list[Tag]] = {tid: [] for tid in transcript_ids}
        for row in rows:
            transcript_id = row["transcript_id"]
            by_transcript[transcript_id].append(
                Tag(
                    id=row["id"],
                    name=row["name"],
                    color=row["color"],
                    is_system=bool(row["is_system"]),
                    created_at=row["created_at"],
                )
            )

        return by_transcript

    # --- Helpers ---

    @staticmethod
    def _row_to_transcript(row: sqlite3.Row) -> Transcript:
        return Transcript(
            id=row["id"],
            timestamp=row["timestamp"],
            raw_text=row["raw_text"],
            normalized_text=row["normalized_text"],
            display_name=row["display_name"],
            duration_ms=row["duration_ms"],
            speech_duration_ms=row["speech_duration_ms"],
            transcription_time_ms=row["transcription_time_ms"],
            refinement_time_ms=row["refinement_time_ms"],
            transcription_provider=row["transcription_provider"],
            transcription_model_id=row["transcription_model_id"],
            transcription_resolved_device=row["transcription_resolved_device"],
            transcription_compute_type=row["transcription_compute_type"],
            transcription_cpu_threads=row["transcription_cpu_threads"],
            transcription_prompt_text=row["transcription_prompt_text"],
            transcription_prompt_chars=row["transcription_prompt_chars"],
            transcription_prompt_words=row["transcription_prompt_words"],
            retranscription_count=row["retranscription_count"],
            last_retranscription_at=row["last_retranscription_at"],
            last_retranscription_time_ms=row["last_retranscription_time_ms"],
            last_retranscription_provider=row["last_retranscription_provider"],
            last_retranscription_model_id=row["last_retranscription_model_id"],
            last_retranscription_resolved_device=row["last_retranscription_resolved_device"],
            last_retranscription_compute_type=row["last_retranscription_compute_type"],
            last_retranscription_cpu_threads=row["last_retranscription_cpu_threads"],
            last_retranscription_prompt_text=row["last_retranscription_prompt_text"],
            last_retranscription_prompt_chars=row["last_retranscription_prompt_chars"],
            last_retranscription_prompt_words=row["last_retranscription_prompt_words"],
            refinement_provider=row["refinement_provider"],
            refinement_model_id=row["refinement_model_id"],
            refinement_resolved_device=row["refinement_resolved_device"],
            refinement_compute_type=row["refinement_compute_type"],
            refinement_cpu_threads=row["refinement_cpu_threads"],
            refinement_gpu_layers=row["refinement_gpu_layers"],
            refinement_use_thinking=bool(row["refinement_use_thinking"]),
            refinement_prompt_text=row["refinement_prompt_text"],
            refinement_prompt_chars=row["refinement_prompt_chars"],
            refinement_prompt_words=row["refinement_prompt_words"],
            refinement_prompt_tokens=row["refinement_prompt_tokens"],
            refinement_completion_tokens=row["refinement_completion_tokens"],
            refinement_total_tokens=row["refinement_total_tokens"],
            created_at=row["created_at"],
            include_in_analytics=bool(row["include_in_analytics"]),
            has_audio_cached=bool(row["has_audio_cached"]),
            is_protected=bool(row["is_protected"]),
            compound_root_id=row["compound_root_id"],
            compound_order=row["compound_order"],
        )

    @staticmethod
    def _row_to_recording_session(row: sqlite3.Row) -> RecordingSessionRecord:
        return RecordingSessionRecord(
            id=row["id"],
            status=row["status"],
            started_at=row["started_at"],
            updated_at=row["updated_at"],
            finalized_at=row["finalized_at"],
            sample_rate=row["sample_rate"],
            channels=row["channels"],
            sample_width_bytes=row["sample_width_bytes"],
            duration_ms=row["duration_ms"],
            frame_count=row["frame_count"],
            byte_count=row["byte_count"],
            last_durable_chunk=row["last_durable_chunk"],
            audio_path=row["audio_path"],
            encrypted=bool(row["encrypted"]),
            encryption_key_id=row["encryption_key_id"],
            transcript_id=row["transcript_id"],
            failure_reason=row["failure_reason"],
        )

    @staticmethod
    def _row_to_audio_asset(row: sqlite3.Row) -> AudioAsset:
        return AudioAsset(
            id=row["id"],
            recording_id=row["recording_id"],
            transcript_id=row["transcript_id"],
            role=row["role"],
            path=row["path"],
            duration_ms=row["duration_ms"],
            size_bytes=row["size_bytes"],
            encrypted=bool(row["encrypted"]),
            pinned=bool(row["pinned"]),
            retain_until=row["retain_until"],
            created_at=row["created_at"],
        )

    def append_to_transcript(
        self,
        transcript_id: int,
        source_transcript_id: int,
    ) -> int | None:
        """Attach a source transcript to a compound rooted at *transcript_id*."""
        with self._write_lock:
            target_row = self._conn.execute(
                "SELECT * FROM transcripts WHERE id = ?",
                (transcript_id,),
            ).fetchone()
            source_row = self._conn.execute(
                "SELECT * FROM transcripts WHERE id = ?",
                (source_transcript_id,),
            ).fetchone()
            if target_row is None or source_row is None:
                return None

            root_id = target_row["compound_root_id"] or target_row["id"]
            if source_row["id"] == root_id:
                return root_id
            if source_row["compound_root_id"] == root_id:
                return root_id
            if source_row["compound_root_id"] is not None:
                logger.warning(
                    "Refusing to append compound child transcript %s into root %s",
                    source_transcript_id,
                    root_id,
                )
                return root_id

            root_row = target_row
            if target_row["id"] != root_id:
                root_row = self._conn.execute(
                    "SELECT * FROM transcripts WHERE id = ?",
                    (root_id,),
                ).fetchone()
                if root_row is None:
                    return None

            descendants = self._conn.execute(
                "SELECT id, compound_order FROM transcripts WHERE compound_root_id = ? ORDER BY compound_order",
                (source_transcript_id,),
            ).fetchall()
            next_order_row = self._conn.execute(
                "SELECT COALESCE(MAX(compound_order), 0) AS max_order FROM transcripts WHERE compound_root_id = ?",
                (root_id,),
            ).fetchone()
            next_order = int(next_order_row["max_order"] or 0) + 1

            source_display_text = source_row["normalized_text"] or source_row["raw_text"] or ""
            new_raw = self._append_text(root_row["raw_text"] or "", source_row["raw_text"] or "")
            current_norm: str = root_row["normalized_text"] or ""
            new_norm = self._append_text(current_norm, source_display_text) if current_norm else ""
            self._conn.execute(
                """UPDATE transcripts
                   SET raw_text = ?, normalized_text = ?,
                       duration_ms = duration_ms + ?,
                       speech_duration_ms = speech_duration_ms + ?
                   WHERE id = ?""",
                (
                    new_raw,
                    new_norm,
                    int(source_row["duration_ms"] or 0),
                    int(source_row["speech_duration_ms"] or 0),
                    root_id,
                ),
            )

            self._conn.execute(
                "UPDATE transcripts SET compound_root_id = ?, compound_order = ? WHERE id = ?",
                (root_id, next_order, source_transcript_id),
            )
            for child in descendants:
                self._conn.execute(
                    "UPDATE transcripts SET compound_root_id = ?, compound_order = ? WHERE id = ?",
                    (root_id, next_order + int(child["compound_order"] or 0), child["id"]),
                )
            self._conn.commit()
        self.add_system_tag_to_transcript(root_id, "Compound")
        return root_id

    def set_analytics_inclusion(self, transcript_id: int, include: bool) -> None:
        """Set the include_in_analytics flag for a transcript."""
        with self._write_lock:
            self._conn.execute(
                "UPDATE transcripts SET include_in_analytics = ? WHERE id = ?",
                (1 if include else 0, transcript_id),
            )
            self._conn.commit()

    def set_audio_cached(self, transcript_id: int, cached: bool) -> None:
        """Set the has_audio_cached flag for a transcript."""
        with self._write_lock:
            self._conn.execute(
                "UPDATE transcripts SET has_audio_cached = ? WHERE id = ?",
                (1 if cached else 0, transcript_id),
            )
            self._conn.commit()

    # --- Durable audio recordings ---

    def create_recording_session(
        self,
        *,
        recording_id: str,
        audio_path: Path | str,
        sample_rate: int,
        channels: int = 1,
        sample_width_bytes: int = 2,
        encrypted: bool = False,
        encryption_key_id: str | None = None,
    ) -> RecordingSessionRecord:
        """Create the durable manifest row before microphone capture starts."""
        now = utc_now()
        with self._write_lock, self._conn:
            self._conn.execute(
                """INSERT INTO recording_sessions
                   (id, status, started_at, updated_at, sample_rate, channels,
                    sample_width_bytes, audio_path, encrypted, encryption_key_id)
                   VALUES (?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    recording_id,
                    now,
                    now,
                    int(sample_rate),
                    int(channels),
                    int(sample_width_bytes),
                    str(audio_path),
                    1 if encrypted else 0,
                    encryption_key_id,
                ),
            )
        record = self.get_recording_session(recording_id)
        assert record is not None
        return record

    def add_recording_chunk(
        self,
        *,
        recording_id: str,
        chunk_index: int,
        start_frame: int,
        frame_count: int,
        byte_offset: int,
        byte_count: int,
        sha256: str,
    ) -> None:
        """Record that a chunk is flushed to disk and update session counters."""
        now = utc_now()
        duration_ms = int(((start_frame + frame_count) / 16000) * 1000)
        with self._write_lock, self._conn:
            row = self._conn.execute(
                "SELECT sample_rate FROM recording_sessions WHERE id = ?",
                (recording_id,),
            ).fetchone()
            if row is not None and int(row["sample_rate"] or 0) > 0:
                duration_ms = int(((start_frame + frame_count) / int(row["sample_rate"])) * 1000)
            self._conn.execute(
                """INSERT OR REPLACE INTO recording_chunks
                   (recording_id, chunk_index, start_frame, frame_count,
                    byte_offset, byte_count, sha256, written_at, fsynced_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    recording_id,
                    int(chunk_index),
                    int(start_frame),
                    int(frame_count),
                    int(byte_offset),
                    int(byte_count),
                    sha256,
                    now,
                    now,
                ),
            )
            self._conn.execute(
                """UPDATE recording_sessions
                   SET updated_at = ?, duration_ms = ?, frame_count = ?, byte_count = ?,
                       last_durable_chunk = MAX(last_durable_chunk, ?)
                   WHERE id = ?""",
                (
                    now,
                    duration_ms,
                    int(start_frame + frame_count),
                    int(byte_offset + byte_count),
                    int(chunk_index),
                    recording_id,
                ),
            )

    def mark_recording_status(
        self,
        recording_id: str,
        status: str,
        *,
        transcript_id: int | None = None,
        failure_reason: str | None = None,
        finalized: bool = False,
    ) -> None:
        """Update a durable recording session's lifecycle state."""
        now = utc_now()
        assignments = ["status = ?", "updated_at = ?"]
        params: list[object] = [status, now]
        if finalized:
            assignments.append("finalized_at = ?")
            params.append(now)
        if transcript_id is not None:
            assignments.append("transcript_id = ?")
            params.append(transcript_id)
        if failure_reason is not None:
            assignments.append("failure_reason = ?")
            params.append(failure_reason)
        params.append(recording_id)
        with self._write_lock, self._conn:
            self._conn.execute(
                f"UPDATE recording_sessions SET {', '.join(assignments)} WHERE id = ?",
                tuple(params),
            )

    def get_recording_session(self, recording_id: str) -> RecordingSessionRecord | None:
        with self._write_lock:
            row = self._conn.execute(
                "SELECT * FROM recording_sessions WHERE id = ?",
                (recording_id,),
            ).fetchone()
        return self._row_to_recording_session(row) if row is not None else None

    def list_recording_sessions(self, statuses: tuple[str, ...] | None = None) -> list[RecordingSessionRecord]:
        with self._write_lock:
            if statuses:
                placeholders = ",".join("?" * len(statuses))
                rows = self._conn.execute(
                    f"SELECT * FROM recording_sessions WHERE status IN ({placeholders}) ORDER BY started_at DESC",
                    statuses,
                ).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM recording_sessions ORDER BY started_at DESC").fetchall()
        return [self._row_to_recording_session(row) for row in rows]

    def list_recoverable_recordings(self) -> list[RecordingSessionRecord]:
        """Return recordings that still need user-visible recovery handling."""
        return self.list_recording_sessions(("active", "stopping", "recorded", "transcribing", "recovered", "failed"))

    def add_audio_asset(
        self,
        *,
        recording_id: str | None,
        transcript_id: int | None,
        role: str,
        path: Path | str,
        duration_ms: int,
        size_bytes: int,
        encrypted: bool = False,
        pinned: bool = False,
        retain_until: str | None = None,
    ) -> AudioAsset:
        with self._write_lock, self._conn:
            cur = self._conn.execute(
                """INSERT INTO audio_assets
                   (recording_id, transcript_id, role, path, duration_ms, size_bytes,
                    encrypted, pinned, retain_until)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    recording_id,
                    transcript_id,
                    role,
                    str(path),
                    int(duration_ms),
                    int(size_bytes),
                    1 if encrypted else 0,
                    1 if pinned else 0,
                    retain_until,
                ),
            )
            asset_id = cur.lastrowid
            assert asset_id is not None
            row = self._conn.execute("SELECT * FROM audio_assets WHERE id = ?", (asset_id,)).fetchone()
        return self._row_to_audio_asset(row)

    def get_audio_assets_for_transcript(self, transcript_id: int) -> list[AudioAsset]:
        with self._write_lock:
            rows = self._conn.execute(
                "SELECT * FROM audio_assets WHERE transcript_id = ? ORDER BY created_at DESC",
                (transcript_id,),
            ).fetchall()
        return [self._row_to_audio_asset(row) for row in rows]

    def export_backup(self, dest: Path) -> None:
        """Export a full database backup to dest path."""
        import shutil

        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        shutil.copy2(self._path, dest)

    def transcript_count(self, *, include_compound_children: bool = False, include_protected: bool = False) -> int:
        with self._write_lock:
            conditions: list[str] = []
            if not include_compound_children:
                conditions.append("compound_root_id IS NULL")
            if not include_protected:
                conditions.append("is_protected = 0")
            where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            row = self._conn.execute(f"SELECT COUNT(*) FROM transcripts{where}").fetchone()
        return row[0] if row else 0
