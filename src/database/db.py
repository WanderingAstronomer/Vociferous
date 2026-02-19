"""
Vociferous Database — Raw sqlite3 + dataclasses.

3 tables, WAL mode, ~120 lines. Replaces SQLAlchemy ORM.
"""

from __future__ import annotations

import enum
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.core.resource_manager import ResourceManager

logger = logging.getLogger(__name__)


class _Unset(enum.Enum):
    """Sentinel for distinguishing 'not provided' from None."""

    TOKEN = 0


_UNSET = _Unset.TOKEN


# --- Dataclass Models ---


def utc_now() -> str:
    """ISO-format UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Project:
    id: int | None = None
    name: str = ""
    color: str | None = None
    parent_id: int | None = None
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
    project_id: int | None = None
    current_variant_id: int | None = None
    created_at: str = ""
    # Populated by joins, not stored in transcripts table
    variants: list[TranscriptVariant] = field(default_factory=list)
    project_name: str | None = None

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
        project_id: int | None = None,
        display_name: str | None = None,
    ) -> Transcript:
        """Insert a new transcript and its raw variant. Returns the created transcript."""
        ts = utc_now()
        norm = normalized_text if normalized_text is not None else raw_text
        with self._write_lock:
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
                    project_id,
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
            self._conn.commit()

        return Transcript(
            id=tid,
            timestamp=ts,
            raw_text=raw_text,
            normalized_text=norm,
            display_name=display_name,
            duration_ms=duration_ms,
            speech_duration_ms=speech_duration_ms,
            project_id=project_id,
            current_variant_id=vid,
            created_at=ts,
        )

    def get_transcript(self, transcript_id: int) -> Transcript | None:
        """Get a single transcript with its variants."""
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
        return t

    def recent(self, limit: int = 50, project_id: int | None = None) -> list[Transcript]:
        """Get recent transcripts, newest first."""
        if project_id is not None:
            rows = self._conn.execute(
                """SELECT t.*, p.name as project_name
                   FROM transcripts t
                   LEFT JOIN projects p ON t.project_id = p.id
                   WHERE t.project_id = ?
                   ORDER BY t.created_at DESC LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT t.*, p.name as project_name
                   FROM transcripts t
                   LEFT JOIN projects p ON t.project_id = p.id
                   ORDER BY t.created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [self._row_to_transcript(r) for r in rows]

    def search(self, query: str, limit: int = 50) -> list[Transcript]:
        """Full-text search across transcript text."""
        pattern = f"%{query}%"
        rows = self._conn.execute(
            """SELECT t.*, p.name as project_name
               FROM transcripts t
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE t.raw_text LIKE ? OR t.normalized_text LIKE ?
               ORDER BY t.created_at DESC LIMIT ?""",
            (pattern, pattern, limit),
        ).fetchall()
        return [self._row_to_transcript(r) for r in rows]

    def delete_transcript(self, transcript_id: int) -> bool:
        """Delete a transcript and its variants (CASCADE)."""
        with self._write_lock:
            cur = self._conn.execute("DELETE FROM transcripts WHERE id = ?", (transcript_id,))
            self._conn.commit()
            return cur.rowcount > 0

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
        rows = self._conn.execute(
            """SELECT t.*, p.name as project_name
               FROM transcripts t
               LEFT JOIN projects p ON t.project_id = p.id
               WHERE t.display_name IS NULL OR TRIM(t.display_name) = ''
               ORDER BY t.created_at DESC""",
        ).fetchall()
        return [self._row_to_transcript(r) for r in rows]

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

    # --- Projects ---

    def add_project(self, name: str, *, color: str | None = None, parent_id: int | None = None) -> Project:
        ts = utc_now()
        with self._write_lock:
            cur = self._conn.execute(
                "INSERT INTO projects (name, color, parent_id, created_at) VALUES (?, ?, ?, ?)",
                (name, color, parent_id, ts),
            )
            self._conn.commit()
            return Project(id=cur.lastrowid, name=name, color=color, parent_id=parent_id, created_at=ts)

    def get_projects(self) -> list[Project]:
        rows = self._conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
        return [
            Project(
                id=r["id"],
                name=r["name"],
                color=r["color"],
                parent_id=r["parent_id"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def delete_project(
        self,
        project_id: int,
        *,
        delete_transcripts: bool = False,
        promote_subprojects: bool = True,
        delete_subproject_transcripts: bool = False,
    ) -> bool:
        with self._write_lock:
            # Collect child project IDs
            child_ids = [
                r["id"]
                for r in self._conn.execute("SELECT id FROM projects WHERE parent_id = ?", (project_id,)).fetchall()
            ]

            if child_ids:
                if promote_subprojects:
                    # Promote children to top-level
                    self._conn.execute(
                        "UPDATE projects SET parent_id = NULL WHERE parent_id = ?",
                        (project_id,),
                    )
                else:
                    # Delete subprojects and handle their transcripts
                    placeholders = ",".join("?" * len(child_ids))
                    if delete_subproject_transcripts:
                        self._conn.execute(
                            f"DELETE FROM transcripts WHERE project_id IN ({placeholders})",
                            child_ids,
                        )
                    else:
                        self._conn.execute(
                            f"UPDATE transcripts SET project_id = NULL WHERE project_id IN ({placeholders})",
                            child_ids,
                        )
                    self._conn.execute(
                        f"DELETE FROM projects WHERE id IN ({placeholders})",
                        child_ids,
                    )

            # Handle this project's own transcripts
            if delete_transcripts:
                self._conn.execute(
                    "DELETE FROM transcripts WHERE project_id = ?",
                    (project_id,),
                )
            else:
                self._conn.execute(
                    "UPDATE transcripts SET project_id = NULL WHERE project_id = ?",
                    (project_id,),
                )

            cur = self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def get_project(self, project_id: int) -> Project | None:
        """Fetch a single project by ID."""
        row = self._conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            return None
        return Project(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            parent_id=row["parent_id"],
            created_at=row["created_at"],
        )

    def update_project(
        self,
        project_id: int,
        *,
        name: str | None = None,
        color: str | None = None,
        parent_id: int | None | _Unset = _UNSET,
    ) -> Project | None:
        """Update project fields. Pass parent_id=None to move to root. Omit to leave unchanged."""
        updates: list[str] = []
        params: list[str | int | None] = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if color is not None:
            updates.append("color = ?")
            params.append(color)
        if not isinstance(parent_id, _Unset):
            updates.append("parent_id = ?")
            params.append(parent_id)
        if not updates:
            return self.get_project(project_id)
        params.append(project_id)
        with self._write_lock:
            self._conn.execute(
                f"UPDATE projects SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            self._conn.commit()
        return self.get_project(project_id)

    def assign_project(self, transcript_id: int, project_id: int | None) -> None:
        """Assign (or unassign) a transcript to a project."""
        with self._write_lock:
            self._conn.execute(
                "UPDATE transcripts SET project_id = ? WHERE id = ?",
                (project_id, transcript_id),
            )
            self._conn.commit()

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
        row = self._conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()
        return row[0] if row else 0
