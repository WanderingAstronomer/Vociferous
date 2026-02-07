"""
Transcription history management.

Acts as a Facade over the persistence layer (DatabaseCore, Repositories).
Maintains backward compatibility for UI and other consumers.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject

# Import DTO to re-export it for consumers
from src.database.dtos import HistoryEntry
from src.database.core import DatabaseCore
from src.database.repositories import TranscriptRepository, ProjectRepository
from src.database.signal_bridge import DatabaseSignalBridge
from src.database.events import ChangeAction, EntityChange
from src.ui.constants import HISTORY_EXPORT_LIMIT
from src.ui.utils import format_day_header, format_time
from src.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class HistoryManager(QObject):
    """
    Facade for history management.
    Delegates persistence to TranscriptRepository and ProjectRepository.
    """

    def __init__(self, db_path: Path | None = None, history_file: Path | None = None):
        super().__init__()
        # Support legacy argument for backward compatibility
        final_path = db_path or history_file

        try:
            # Initialize Database Core
            self.db = DatabaseCore(final_path)

            # Initialize Repositories
            self.transcripts = TranscriptRepository(self.db)
            self.projects = ProjectRepository(self.db)

            # Initialize Signal Bridge
            self.bridge = DatabaseSignalBridge()
        except Exception as e:
            raise DatabaseError(
                f"Failed to initialize history database: {e}",
                context={"path": str(final_path)},
            ) from e

    # ========== Transcript Methods ==========

    def add_entry(
        self, text: str, duration_ms: int = 0, speech_duration_ms: int = 0
    ) -> HistoryEntry:
        """Add a new history entry."""
        entry = self.transcripts.add_entry(text, duration_ms, speech_duration_ms)
        self.bridge.emit_change(
            EntityChange(
                entity_type="transcription", action=ChangeAction.CREATED, ids=[entry.id]
            )
        )
        return entry

    def get_entry(self, transcript_id: int) -> HistoryEntry | None:
        return self.transcripts.get_entry(transcript_id)

    def get_entry_by_timestamp(self, timestamp: str) -> HistoryEntry | None:
        return self.transcripts.get_entry_by_timestamp(timestamp)

    def get_id_by_timestamp(self, timestamp: str) -> int | None:
        return self.transcripts.get_id_by_timestamp(timestamp)

    def get_transcript_variants(self, transcript_id: int) -> list[dict]:
        return self.transcripts.get_transcript_variants(transcript_id)

    def add_variant_atomic(
        self, transcript_id: int, text: str, kind: str, model_id: str | None = None
    ) -> bool:
        """Add a transcript variant (e.g., refined text)."""
        success = self.transcripts.add_variant_atomic(
            transcript_id, text, kind, model_id
        )
        if success:
            self.bridge.emit_change(
                EntityChange(
                    entity_type="transcription",
                    action=ChangeAction.UPDATED,
                    ids=[transcript_id],
                )
            )
        return success

    def get_recent(self, limit: int = 100) -> list[HistoryEntry]:
        return self.transcripts.get_recent(limit)

    def search(
        self, query: str, scope: str = "all", limit: int = 100
    ) -> list[HistoryEntry]:
        return self.transcripts.search(query, scope, limit)

    def update_entry(self, timestamp: str, new_text: str) -> bool:
        """Update entry text by timestamp."""
        entry_id = self.get_id_by_timestamp(timestamp)
        success = self.transcripts.update_entry(timestamp, new_text)
        if success and entry_id is not None:
            self.bridge.emit_change(
                EntityChange(
                    entity_type="transcription",
                    action=ChangeAction.UPDATED,
                    ids=[entry_id],
                )
            )
        return success

    def update_text(self, transcript_id: int, new_text: str) -> bool:
        """Update text by transcript ID (convenience method)."""
        # We don't need to emit here because update_entry (called below) handles it
        # BUT wait, update_entry works by timestamp.
        entry = self.get_entry(transcript_id)
        if entry:
            return self.update_entry(entry.timestamp, new_text)
        return False

    def update_normalized_text(self, transcript_id: int, new_text: str) -> bool:
        """
        Update the normalized (mutable) text for a transcript.
        Alias for update_text to satisfy strict API contracts.
        """
        return self.update_text(transcript_id, new_text)

    def delete_entry(self, timestamp: str) -> bool:
        """Delete an entry by timestamp."""
        entry_id = self.get_id_by_timestamp(timestamp)
        success = self.transcripts.delete_entry(timestamp)
        if success and entry_id is not None:
            self.bridge.emit_change(
                EntityChange(
                    entity_type="transcription",
                    action=ChangeAction.DELETED,
                    ids=[entry_id],
                )
            )
        return success

    def clear(self) -> None:
        """Clear all history entries."""
        self.transcripts.clear()
        self.bridge.emit_change(
            EntityChange(
                entity_type="transcription",
                action=ChangeAction.DELETED,
                ids=[],
                reload_required=True,
            )
        )

    # ========== Export Logic (Application Layer) ==========

    def export_to_file(self, export_path: Path, format: str = "txt") -> bool:
        """Export history to file."""
        entries = self.transcripts.get_recent(limit=HISTORY_EXPORT_LIMIT)

        try:
            with open(export_path, "w", encoding="utf-8") as f:
                match format:
                    case "txt":
                        for entry in entries:
                            f.write(f"[{entry.timestamp}]\n{entry.text}\n\n")

                    case "csv":
                        writer = csv.writer(f)
                        writer.writerow(["Timestamp", "Text", "Duration (ms)"])
                        for entry in entries:
                            writer.writerow(
                                [entry.timestamp, entry.text, entry.duration_ms]
                            )

                    case "md":
                        f.write("# Vociferous Transcription History\n\n")
                        current_day = None
                        for entry in entries:
                            dt = datetime.fromisoformat(entry.timestamp)
                            day_key = dt.date().isoformat()

                            if current_day != day_key:
                                current_day = day_key
                                f.write(
                                    f"## {format_day_header(dt, include_year=True)}\n\n"
                                )

                            f.write(f"### {format_time(dt)}\n\n")
                            f.write(f"{entry.text}\n\n")

                            if entry.duration_ms > 0:
                                f.write(f"*Duration: {entry.duration_ms}ms*\n\n")

                            f.write("---\n\n")

                    case _:
                        logger.error(f"Unknown export format: {format}")
                        return False

            logger.info(f"Exported {len(entries)} entries to {export_path}")
            return True

        except OSError as e:
            logger.error(f"Export failed: {e}")
            return False

    def backup_database(self, dest: Path) -> bool:
        """Copy the SQLite database file to *dest* for backup.

        Uses SQLite's VACUUM INTO for a consistent, self-contained copy that
        does not interfere with ongoing writes (WAL-safe).  Falls back to a
        plain file copy if VACUUM INTO is unavailable.
        """
        import shutil
        from sqlalchemy import text as sa_text

        try:
            dest = Path(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)

            try:
                with self.db.engine.connect() as conn:
                    conn.execute(sa_text(f"VACUUM INTO '{dest}'"))
                    conn.commit()
            except Exception:
                # Fallback: plain copy (safe when WAL is checkpointed)
                logger.warning("VACUUM INTO unavailable, falling back to file copy")
                with self.db.engine.connect() as conn:
                    conn.execute(sa_text("PRAGMA wal_checkpoint(TRUNCATE)"))
                    conn.commit()
                shutil.copy2(self.db.db_path, dest)

            logger.info("Database backup created: %s", dest)
            return True
        except Exception as e:
            logger.error("Database backup failed: %s", e)
            return False

    # ========== Project Methods ==========

    def create_project(
        self, name: str, color: str | None = None, parent_id: int | None = None
    ) -> int | None:
        """Create a new project."""
        project_id = self.projects.create(name, color, parent_id)
        if project_id is not None:
            self.bridge.emit_change(
                EntityChange(
                    entity_type="project", action=ChangeAction.CREATED, ids=[project_id]
                )
            )
        return project_id

    def get_projects(self) -> list[tuple[int, str, str | None, int | None]]:
        return self.projects.get_all()

    def rename_project(self, project_id: int, new_name: str) -> bool:
        """Rename a project."""
        success = self.projects.rename(project_id, new_name)
        if success:
            self.bridge.emit_change(
                EntityChange(
                    entity_type="project", action=ChangeAction.UPDATED, ids=[project_id]
                )
            )
        return success

    def update_project_color(self, project_id: int, color: str | None) -> bool:
        """Update project color."""
        success = self.projects.update_color(project_id, color)
        if success:
            self.bridge.emit_change(
                EntityChange(
                    entity_type="project", action=ChangeAction.UPDATED, ids=[project_id]
                )
            )
        return success

    def delete_project(self, project_id: int, move_to_unassigned: bool = True) -> bool:
        """Delete a project."""
        success = self.projects.delete(project_id, move_to_unassigned)
        if success:
            self.bridge.emit_change(
                EntityChange(
                    entity_type="project", action=ChangeAction.DELETED, ids=[project_id]
                )
            )
        return success

    def assign_transcript_to_project(
        self, timestamp: str, project_id: int | None
    ) -> bool:
        """Assign a transcript to a project."""
        entry_id = self.get_id_by_timestamp(timestamp)
        success = self.transcripts.assign_to_project(timestamp, project_id)
        if success and entry_id is not None:
            self.bridge.emit_change(
                EntityChange(
                    entity_type="transcription",
                    action=ChangeAction.UPDATED,
                    ids=[entry_id],
                )
            )
        return success

    def get_transcripts_by_project(
        self, project_id: int | None, limit: int = 100
    ) -> list[HistoryEntry]:
        return self.transcripts.get_by_project(project_id, limit)

    def get_project_counts(self) -> dict[int | None, int]:
        return self.transcripts.get_project_counts()

    def get_project_colors(self) -> dict[int, str | None]:
        return self.projects.get_colors()
