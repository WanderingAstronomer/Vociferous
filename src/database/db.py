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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.core.resource_manager import ResourceManager

logger = logging.getLogger(__name__)


# --- Dataclass Models ---


def utc_now() -> str:
    """ISO-format UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Tag:
    id: int | None = None
    name: str = ""
    color: str | None = None
    is_system: bool = False
    created_at: str = ""


@dataclass(slots=True)
class Transcript:
    id: int | None = None
    timestamp: str = ""
    raw_text: str = ""
    normalized_text: str = ""
    display_name: str | None = None
    duration_ms: int = 0
    speech_duration_ms: int = 0
    created_at: str = ""
    # Populated by joins, not stored in transcripts table
    tags: list[Tag] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Current display text: normalized_text (edited/refined) or raw_text."""
        return self.normalized_text or self.raw_text


# --- Database ---


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT UNIQUE NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    display_name TEXT,
    duration_ms INTEGER DEFAULT 0,
    speech_duration_ms INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
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
        display_name: str | None = None,
        tag_ids: list[int] | None = None,
    ) -> Transcript:
        """Insert a new transcript. Returns the created transcript."""
        ts = utc_now()
        norm = normalized_text if normalized_text is not None else raw_text
        with self._write_lock, self._conn:
            cur = self._conn.execute(
                """INSERT INTO transcripts
                   (timestamp, raw_text, normalized_text, display_name,
                    duration_ms, speech_duration_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    ts,
                    raw_text,
                    norm,
                    display_name,
                    duration_ms,
                    speech_duration_ms,
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
            created_at=ts,
            tags=tags,
        )

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

    def recent(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        tag_ids: list[int] | None = None,
        tag_mode: str = "any",
    ) -> tuple[list[Transcript], int]:
        """Get transcripts with pagination and sorting.

        Args:
            limit: Max results per page.
            offset: Number of results to skip.
            sort_by: Column to sort by (created_at, duration_ms, speech_duration_ms, display_name).
            sort_dir: "asc" or "desc".
            tag_ids: Filter to transcripts having these tags.
            tag_mode: "any" = match any tag, "all" = must have all tags.

        Returns:
            Tuple of (transcripts, total_count).
        """
        col = sort_by if sort_by in self._SORT_COLUMNS else "created_at"
        expr = self._SORT_EXPRESSIONS[col]
        direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
        order_clause = f"ORDER BY {expr} {direction}"

        with self._write_lock:
            if tag_ids:
                if tag_mode == "all":
                    placeholders = ",".join("?" * len(tag_ids))
                    where = f"""WHERE t.id IN (
                               SELECT transcript_id FROM transcript_tags
                               WHERE tag_id IN ({placeholders})
                               GROUP BY transcript_id
                               HAVING COUNT(DISTINCT tag_id) = ?
                           )"""
                    count_params: tuple = (*tag_ids, len(tag_ids))
                    query_params: tuple = (*tag_ids, len(tag_ids), limit, offset)

                    total = self._conn.execute(
                        f"""SELECT COUNT(*) FROM transcripts t {where}""",
                        count_params,
                    ).fetchone()[0]

                    rows = self._conn.execute(
                        f"""SELECT t.*
                           FROM transcripts t
                           {where}
                           {order_clause} LIMIT ? OFFSET ?""",
                        query_params,
                    ).fetchall()
                else:
                    placeholders = ",".join("?" * len(tag_ids))
                    where = f"""INNER JOIN transcript_tags tt ON t.id = tt.transcript_id
                           WHERE tt.tag_id IN ({placeholders})"""
                    count_params = tuple(tag_ids)
                    query_params = (*tag_ids, limit, offset)

                    total = self._conn.execute(
                        f"""SELECT COUNT(DISTINCT t.id) FROM transcripts t {where}""",
                        count_params,
                    ).fetchone()[0]

                    rows = self._conn.execute(
                        f"""SELECT DISTINCT t.*
                           FROM transcripts t
                           {where}
                           {order_clause} LIMIT ? OFFSET ?""",
                        query_params,
                    ).fetchall()
            else:
                total = self._conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
                rows = self._conn.execute(
                    f"""SELECT t.*
                       FROM transcripts t
                       {order_clause} LIMIT ? OFFSET ?""",
                    (limit, offset),
                ).fetchall()
            transcripts = [self._row_to_transcript(r) for r in rows]
            # Populate tags for each transcript
            for transcript in transcripts:
                assert transcript.id is not None
                transcript.tags = self._get_tags_for_transcript(transcript.id)
        return transcripts, total

    def search(self, query: str, limit: int = 50, offset: int = 0) -> list[Transcript]:
        """Full-text search across transcript text using FTS5.

        An empty *query* returns the most-recent transcripts (same as
        ``recent(limit=limit)``). Multi-word queries are split on whitespace
        and each token is matched as a prefix, so ``"py prog"`` finds
        "Python programming".
        """
        if not query.strip():
            items, _ = self.recent(limit=limit, offset=offset)
            return items
        tokens = query.split()
        # Wrap each token in double-quotes (FTS5 phrase) with prefix wildcard.
        # Inner double-quotes are escaped by doubling them per FTS5 syntax.
        fts_terms = " ".join(f'"{token.replace(chr(34), "")}"*' for token in tokens)
        with self._write_lock:
            rows = self._conn.execute(
                """SELECT t.*
                   FROM transcripts t
                   WHERE t.id IN (SELECT rowid FROM transcripts_fts WHERE transcripts_fts MATCH ?)
                   ORDER BY t.created_at DESC LIMIT ? OFFSET ?""",
                (fts_terms, limit, offset),
            ).fetchall()
            transcripts = [self._row_to_transcript(r) for r in rows]
            for t in transcripts:
                assert t.id is not None
                t.tags = self._get_tags_for_transcript(t.id)
        return transcripts

    def search_count(self, query: str) -> int:
        """Return the total number of transcripts matching *query* (for pagination)."""
        if not query.strip():
            with self._write_lock:
                row = self._conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()
            return row[0] if row else 0
        tokens = query.split()
        fts_terms = " ".join(f'"{t.replace(chr(34), "")}"*' for t in tokens)
        with self._write_lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM transcripts_fts WHERE transcripts_fts MATCH ?",
                (fts_terms,),
            ).fetchone()
        return row[0] if row else 0

    def delete_transcript(self, transcript_id: int) -> bool:
        """Delete a transcript (tag junction rows CASCADE)."""
        with self._write_lock:
            cur = self._conn.execute("DELETE FROM transcripts WHERE id = ?", (transcript_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def batch_delete_transcripts(self, transcript_ids: list[int]) -> int:
        """Delete multiple transcripts in a single transaction. Returns count deleted."""
        if not transcript_ids:
            return 0
        placeholders = ",".join("?" * len(transcript_ids))
        with self._write_lock:
            cur = self._conn.execute(
                f"DELETE FROM transcripts WHERE id IN ({placeholders})",
                transcript_ids,
            )
            self._conn.commit()
            return cur.rowcount

    def clear_all_transcripts(self) -> int:
        """Delete all transcripts. Returns count deleted."""
        with self._write_lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM transcripts")
            count = cur.fetchone()[0]
            # transcript_tags ON DELETE CASCADE handles junction table cleanup
            self._conn.execute("DELETE FROM transcripts")
            self._conn.commit()
            return count

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

    def assign_tags(self, transcript_id: int, tag_ids: list[int]) -> list[Tag]:
        """Set the exact user-tag set for a transcript (preserves system tags)."""
        with self._write_lock:
            # Only remove non-system tags so auto-applied system tags survive
            self._conn.execute(
                """DELETE FROM transcript_tags WHERE transcript_id = ?
                   AND tag_id NOT IN (SELECT id FROM tags WHERE is_system = 1)""",
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

    def add_system_tag_to_transcript(self, transcript_id: int, tag_name: str) -> None:
        """Add a system tag (looked up by name) to a transcript. No-op if tag not found."""
        with self._write_lock:
            row = self._conn.execute(
                "SELECT id FROM tags WHERE name = ? AND is_system = 1",
                (tag_name,),
            ).fetchone()
            if row is None:
                return
            self._conn.execute(
                "INSERT OR IGNORE INTO transcript_tags (transcript_id, tag_id) VALUES (?, ?)",
                (transcript_id, row["id"]),
            )
            self._conn.commit()

    def remove_system_tag_from_transcript(self, transcript_id: int, tag_name: str) -> None:
        """Remove a system tag (looked up by name) from a transcript. No-op if tag not found."""
        with self._write_lock:
            row = self._conn.execute(
                "SELECT id FROM tags WHERE name = ? AND is_system = 1",
                (tag_name,),
            ).fetchone()
            if row is None:
                return
            self._conn.execute(
                "DELETE FROM transcript_tags WHERE transcript_id = ? AND tag_id = ?",
                (transcript_id, row["id"]),
            )
            self._conn.commit()

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
            created_at=row["created_at"],
        )

    def export_backup(self, dest: Path) -> None:
        """Export a full database backup to dest path."""
        import shutil

        self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        shutil.copy2(self._path, dest)

    def transcript_count(self) -> int:
        with self._write_lock:
            row = self._conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()
        return row[0] if row else 0
