"""
Transcription history management.

Acts as a Facade over the persistence layer (DatabaseCore, Repositories).
Maintains backward compatibility for UI and other consumers.
"""

import csv
import logging
from datetime import datetime
from pathlib import Path

# Import DTO to re-export it for consumers
from database.dtos import HistoryEntry
from database.core import DatabaseCore
from database.repositories import TranscriptRepository, ProjectRepository
from ui.constants import HISTORY_EXPORT_LIMIT
from ui.utils import format_day_header, format_time
from exceptions import DatabaseError

logger = logging.getLogger(__name__)

class HistoryManager:
    """
    Facade for history management.
    Delegates persistence to TranscriptRepository and ProjectRepository.
    """

    def __init__(self, db_path: Path | None = None, history_file: Path | None = None):
        # Support legacy argument for backward compatibility
        final_path = db_path or history_file
        
        try:
            # Initialize Database Core
            self.db = DatabaseCore(final_path)
            
            # Initialize Repositories
            self.transcripts = TranscriptRepository(self.db)
            self.projects = ProjectRepository(self.db)
        except Exception as e:
            raise DatabaseError(
                f"Failed to initialize history database: {e}",
                context={"path": str(final_path)}
            ) from e

    # ========== Transcript Methods ==========

    def add_entry(
        self, text: str, duration_ms: int = 0, speech_duration_ms: int = 0
    ) -> HistoryEntry:
        return self.transcripts.add_entry(text, duration_ms, speech_duration_ms)

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
        return self.transcripts.add_variant_atomic(transcript_id, text, kind, model_id)

    def get_recent(self, limit: int = 100) -> list[HistoryEntry]:
        return self.transcripts.get_recent(limit)

    def search(
        self, query: str, scope: str = "all", limit: int = 100
    ) -> list[HistoryEntry]:
        return self.transcripts.search(query, scope, limit)

    def update_entry(self, timestamp: str, new_text: str) -> bool:
        return self.transcripts.update_entry(timestamp, new_text)

    def update_text(self, transcript_id: int, new_text: str) -> bool:
        """Update text by transcript ID (convenience method)."""
        entry = self.get_entry(transcript_id)
        if entry:
            return self.transcripts.update_entry(entry.timestamp, new_text)
        return False

    def delete_entry(self, timestamp: str) -> bool:
        return self.transcripts.delete_entry(timestamp)

    def clear(self) -> None:
        self.transcripts.clear()

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

    # ========== Project Methods ==========

    def create_project(
        self, name: str, color: str | None = None, parent_id: int | None = None
    ) -> int | None:
        return self.projects.create(name, color, parent_id)

    def get_projects(self) -> list[tuple[int, str, str | None, int | None]]:
        return self.projects.get_all()

    def rename_project(self, project_id: int, new_name: str) -> bool:
        return self.projects.rename(project_id, new_name)

    def update_project_color(self, project_id: int, color: str | None) -> bool:
        return self.projects.update_color(project_id, color)

    def delete_project(
        self, project_id: int, move_to_unassigned: bool = True
    ) -> bool:
        return self.projects.delete(project_id, move_to_unassigned)

    def assign_transcript_to_project(
        self, timestamp: str, project_id: int | None
    ) -> bool:
        return self.transcripts.assign_to_project(timestamp, project_id)

    def get_transcripts_by_project(
        self, project_id: int | None, limit: int = 100
    ) -> list[HistoryEntry]:
        return self.transcripts.get_by_project(project_id, limit)

    def get_project_counts(self) -> dict[int | None, int]:
        return self.transcripts.get_project_counts()

    def get_project_colors(self) -> dict[int, str | None]:
        return self.projects.get_colors()
