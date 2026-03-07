"""
Vociferous Database — Raw sqlite3 + dataclasses.

7 tables (tags, transcript_tags, transcripts, transcript_variants,
schema_version, transcripts_fts, plus legacy projects), WAL mode.
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
class Project:
    """Legacy — kept for migration compatibility. Use Tag instead."""

    id: int | None = None
    name: str = ""
    color: str | None = None
    parent_id: int | None = None
    created_at: str = ""


@dataclass(slots=True)
class Tag:
    id: int | None = None
    name: str = ""
    color: str | None = None
    created_at: str = ""


@dataclass(slots=True)
class TranscriptVariant:
    id: int | None = None
    transcript_id: int = 0
    kind: str = "raw"  # 'raw', 'user_edit', 'refined'
    text: str = ""
    model_id: str | None = None
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
    project_id: int | None = None  # Legacy — kept for DB compat, not used in new code
    current_variant_id: int | None = None
    created_at: str = ""
    # Populated by joins, not stored in transcripts table
    variants: list[TranscriptVariant] = field(default_factory=list)
    project_name: str | None = None  # Legacy — kept for compat
    tags: list[Tag] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Current text: variant text if set, else normalized_text."""
        for v in self.variants:
            if v.id == self.current_variant_id:
                return v.text
        return self.normalized_text


# --- Database ---


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    color TEXT,
    parent_id INTEGER REFERENCES projects(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT UNIQUE NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    display_name TEXT,
    duration_ms INTEGER DEFAULT 0,
    speech_duration_ms INTEGER DEFAULT 0,
    project_id INTEGER REFERENCES projects(id),
    current_variant_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE TABLE IF NOT EXISTS transcript_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    model_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON transcripts(timestamp);
CREATE INDEX IF NOT EXISTS idx_transcripts_project ON transcripts(project_id);
CREATE INDEX IF NOT EXISTS idx_variants_transcript ON transcript_variants(transcript_id);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    color TEXT,
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
        """Insert a new transcript and its raw variant. Returns the created transcript."""
        ts = utc_now()
        norm = normalized_text if normalized_text is not None else raw_text
        with self._write_lock, self._conn:
            cur = self._conn.execute(
                """INSERT INTO transcripts
                   (timestamp, raw_text, normalized_text, display_name,
                    duration_ms, speech_duration_ms, project_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ts,
                    raw_text,
                    norm,
                    display_name,
                    duration_ms,
                    speech_duration_ms,
                    None,  # project_id — vestigial column, always NULL for new records
                    ts,
                ),
            )
            tid = cur.lastrowid
            assert tid is not None

            # Create raw variant
            vcur = self._conn.execute(
                """INSERT INTO transcript_variants (transcript_id, kind, text, created_at)
                   VALUES (?, 'raw', ?, ?)""",
                (tid, raw_text, ts),
            )
            vid = vcur.lastrowid
            self._conn.execute("UPDATE transcripts SET current_variant_id = ? WHERE id = ?", (vid, tid))

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
            project_id=None,
            current_variant_id=vid,
            created_at=ts,
            tags=tags,
        )

    def get_transcript(self, transcript_id: int) -> Transcript | None:
        """Get a single transcript with its variants and tags."""
        with self._write_lock:
            row = self._conn.execute(
                """SELECT t.*, p.name as project_name
                   FROM transcripts t
                   LEFT JOIN projects p ON t.project_id = p.id
                   WHERE t.id = ?""",
                (transcript_id,),
            ).fetchone()
            if row is None:
                return None
            t = self._row_to_transcript(row)
            t.variants = self._get_variants(transcript_id)
            t.tags = self._get_tags_for_transcript(transcript_id)
        return t

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
                        f"""SELECT t.*, p.name as project_name
                           FROM transcripts t
                           LEFT JOIN projects p ON t.project_id = p.id
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
                        f"""SELECT DISTINCT t.*, p.name as project_name
                           FROM transcripts t
                           LEFT JOIN projects p ON t.project_id = p.id
                           {where}
                           {order_clause} LIMIT ? OFFSET ?""",
                        query_params,
                    ).fetchall()
            else:
                total = self._conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
                rows = self._conn.execute(
                    f"""SELECT t.*, p.name as project_name
                       FROM transcripts t
                       LEFT JOIN projects p ON t.project_id = p.id
                       {order_clause} LIMIT ? OFFSET ?""",
                    (limit, offset),
                ).fetchall()
            transcripts = [self._row_to_transcript(r) for r in rows]
            # Populate tags for each transcript
            for t in transcripts:
                assert t.id is not None
                t.tags = self._get_tags_for_transcript(t.id)
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
        fts_terms = " ".join(f'"{t.replace(chr(34), "")}"*' for t in tokens)
        with self._write_lock:
            rows = self._conn.execute(
                """SELECT t.*, p.name as project_name
                   FROM transcripts t
                   LEFT JOIN projects p ON t.project_id = p.id
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
        """Delete a transcript and its variants (CASCADE)."""
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
        """Delete all transcripts and their variants. Returns count deleted."""
        with self._write_lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM transcripts")
            count = cur.fetchone()[0]
            # ON DELETE CASCADE handles variants automatically
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

    def get_untitled_transcripts(self) -> list[Transcript]:
        """Get all transcripts that have no display_name set (NULL or empty string)."""
        with self._write_lock:
            rows = self._conn.execute(
                """SELECT t.*, p.name as project_name
                   FROM transcripts t
                   LEFT JOIN projects p ON t.project_id = p.id
                   WHERE t.display_name IS NULL OR TRIM(t.display_name) = ''
                   ORDER BY t.created_at DESC""",
            ).fetchall()
            transcripts = [self._row_to_transcript(r) for r in rows]
            for t in transcripts:
                assert t.id is not None
                t.tags = self._get_tags_for_transcript(t.id)
        return transcripts

    # --- Variants ---

    def add_variant(
        self,
        transcript_id: int,
        kind: str,
        text: str,
        *,
        model_id: str | None = None,
        set_current: bool = True,
    ) -> TranscriptVariant:
        """Add a variant to a transcript. Optionally set as current."""
        ts = utc_now()
        with self._write_lock:
            cur = self._conn.execute(
                """INSERT INTO transcript_variants (transcript_id, kind, text, model_id, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (transcript_id, kind, text, model_id, ts),
            )
            vid = cur.lastrowid
            if set_current:
                self._conn.execute(
                    "UPDATE transcripts SET current_variant_id = ? WHERE id = ?",
                    (vid, transcript_id),
                )
            self._conn.commit()
        return TranscriptVariant(
            id=vid,
            transcript_id=transcript_id,
            kind=kind,
            text=text,
            model_id=model_id,
            created_at=ts,
        )

    def _get_variants(self, transcript_id: int) -> list[TranscriptVariant]:
        rows = self._conn.execute(
            "SELECT * FROM transcript_variants WHERE transcript_id = ? ORDER BY created_at",
            (transcript_id,),
        ).fetchall()
        return [
            TranscriptVariant(
                id=r["id"],
                transcript_id=r["transcript_id"],
                kind=r["kind"],
                text=r["text"],
                model_id=r["model_id"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def delete_variant(self, transcript_id: int, variant_id: int) -> bool:
        """Delete a variant. If it was the current variant, reset to the latest remaining."""
        # Verify the variant belongs to this transcript
        with self._write_lock:
            row = self._conn.execute(
                "SELECT id FROM transcript_variants WHERE id = ? AND transcript_id = ?",
                (variant_id, transcript_id),
            ).fetchone()
            if row is None:
                return False

            self._conn.execute("DELETE FROM transcript_variants WHERE id = ?", (variant_id,))

            # If we just deleted the current variant, point to the latest remaining
            cur_row = self._conn.execute(
                "SELECT current_variant_id FROM transcripts WHERE id = ?", (transcript_id,)
            ).fetchone()
            if cur_row and cur_row["current_variant_id"] == variant_id:
                latest = self._conn.execute(
                    "SELECT id FROM transcript_variants WHERE transcript_id = ? ORDER BY created_at DESC LIMIT 1",
                    (transcript_id,),
                ).fetchone()
                new_current = latest["id"] if latest else None
                self._conn.execute(
                    "UPDATE transcripts SET current_variant_id = ? WHERE id = ?",
                    (new_current, transcript_id),
                )

            self._conn.commit()
            return True

    def prune_refinement_variants(self, transcript_id: int, *, keep: int = 3) -> int:
        """Delete oldest refinement variants beyond *keep* most recent.

        Only targets variants whose ``kind`` starts with ``refinement_``
        (i.e. auto-generated by the refinement pipeline).  User edits and
        other variant kinds are never touched.

        Returns the number of pruned variants.
        """
        with self._write_lock:
            rows = self._conn.execute(
                """SELECT id FROM transcript_variants
                   WHERE transcript_id = ? AND kind LIKE 'refinement_%'
                   ORDER BY created_at DESC""",
                (transcript_id,),
            ).fetchall()

            to_delete = [r["id"] for r in rows[keep:]]
            if not to_delete:
                return 0

            placeholders = ",".join("?" * len(to_delete))
            self._conn.execute(
                f"DELETE FROM transcript_variants WHERE id IN ({placeholders})",
                to_delete,
            )

            # If current_variant_id was among those deleted, reset to latest remaining
            cur_row = self._conn.execute(
                "SELECT current_variant_id FROM transcripts WHERE id = ?", (transcript_id,)
            ).fetchone()
            if cur_row and cur_row["current_variant_id"] in to_delete:
                latest = self._conn.execute(
                    "SELECT id FROM transcript_variants WHERE transcript_id = ? ORDER BY created_at DESC LIMIT 1",
                    (transcript_id,),
                ).fetchone()
                new_current = latest["id"] if latest else None
                self._conn.execute(
                    "UPDATE transcripts SET current_variant_id = ? WHERE id = ?",
                    (new_current, transcript_id),
                )

            self._conn.commit()
            return len(to_delete)

    # --- Tags ---

    def add_tag(self, name: str, *, color: str | None = None) -> Tag:
        """Create a new tag."""
        ts = utc_now()
        with self._write_lock:
            cur = self._conn.execute(
                "INSERT INTO tags (name, color, created_at) VALUES (?, ?, ?)",
                (name, color, ts),
            )
            self._conn.commit()
            return Tag(id=cur.lastrowid, name=name, color=color, created_at=ts)

    def get_tags(self) -> list[Tag]:
        """List all tags ordered by name."""
        with self._write_lock:
            rows = self._conn.execute("SELECT * FROM tags ORDER BY name").fetchall()
        return [Tag(id=r["id"], name=r["name"], color=r["color"], created_at=r["created_at"]) for r in rows]

    def get_tag(self, tag_id: int) -> Tag | None:
        """Fetch a single tag by ID."""
        with self._write_lock:
            row = self._conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
        if row is None:
            return None
        return Tag(id=row["id"], name=row["name"], color=row["color"], created_at=row["created_at"])

    def update_tag(
        self,
        tag_id: int,
        *,
        name: str | None = None,
        color: str | None = None,
    ) -> Tag | None:
        """Update a tag's name and/or color."""
        updates: list[str] = []
        params: list[str | int | None] = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if color is not None:
            updates.append("color = ?")
            params.append(color)
        if not updates:
            return self.get_tag(tag_id)
        params.append(tag_id)
        with self._write_lock:
            self._conn.execute(
                f"UPDATE tags SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            self._conn.commit()
        return self.get_tag(tag_id)

    def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag. Junction rows are cascade-deleted."""
        with self._write_lock:
            cur = self._conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def assign_tags(self, transcript_id: int, tag_ids: list[int]) -> list[Tag]:
        """Set the exact tag set for a transcript (replaces existing)."""
        with self._write_lock:
            self._conn.execute(
                "DELETE FROM transcript_tags WHERE transcript_id = ?",
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

    def _get_tags_for_transcript(self, transcript_id: int) -> list[Tag]:
        """Fetch all tags for a transcript. Caller must hold _write_lock."""
        rows = self._conn.execute(
            """SELECT t.* FROM tags t
               INNER JOIN transcript_tags tt ON t.id = tt.tag_id
               WHERE tt.transcript_id = ?
               ORDER BY t.name""",
            (transcript_id,),
        ).fetchall()
        return [Tag(id=r["id"], name=r["name"], color=r["color"], created_at=r["created_at"]) for r in rows]

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
            project_id=row["project_id"],
            current_variant_id=row["current_variant_id"],
            created_at=row["created_at"],
            project_name=row["project_name"] if "project_name" in row.keys() else None,
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
