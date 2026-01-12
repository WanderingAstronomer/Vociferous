"""
Transcription history management with SQLAlchemy storage.

Replaces raw SQLite storage with ORM-based implementation supporting:
- Immutable raw_text (audit baseline)
- Editable normalized_text (refinement target)
- Focus group membership
- Efficient queries and updates via SQLAlchemy
"""

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, delete, desc, func, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from models import Base, FocusGroup, Transcript, TranscriptVariant
from ui.constants import HISTORY_EXPORT_LIMIT, HISTORY_RECENT_LIMIT
from ui.utils import format_day_header, format_time
from utils import ConfigManager

logger = logging.getLogger(__name__)

# History database location
HISTORY_DIR = Path.home() / ".config" / "vociferous"
HISTORY_DB = HISTORY_DIR / "vociferous.db"


@dataclass(slots=True)
class HistoryEntry:
    """
    Single transcription history entry with timestamp, text, and duration.
    DTO for UI consumption, mapped from Transcript model.
    """

    timestamp: str
    text: str
    duration_ms: int
    speech_duration_ms: int = 0
    focus_group_id: int | None = None

    def to_display_string(self, max_length: int = 80) -> str:
        """Format for display in list widget: [HH:MM:SS] text preview..."""
        # Timestamp expected format: YYYY-MM-DDTHH:MM:SS.mmmmmm or similar
        try:
            timestamp_short = self.timestamp.split("T")[1][:8]  # HH:MM:SS
        except IndexError:
            timestamp_short = self.timestamp[-8:]

        if len(self.text) > max_length:
            text_preview = self.text[:max_length] + "..."
        else:
            text_preview = self.text
        return f"[{timestamp_short}] {text_preview}"


class HistoryManager:
    """
    Manages transcription history with SQLAlchemy storage.

    Provides an interface compatible with the previous raw-SQLite implementation
    but backed by a robust ORM engine.
    """

    def __init__(self, history_file: Path | None = None) -> None:
        """Initialize history manager with optional custom database path."""
        self.history_file = history_file or HISTORY_DB
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        # Create SQLAlchemy engine
        self.engine = create_engine(f"sqlite:///{self.history_file}")
        self.Session = sessionmaker(bind=self.engine)

        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema, handling legacy migration by reset."""
        # Check for legacy schema (schema_version table exists)
        try:
            from sqlalchemy import inspect

            inspector = inspect(self.engine)
            if "schema_version" in inspector.get_table_names():
                logger.info(
                    "Legacy database detected. Performing complete reset (nuke) as requested."
                )
                Base.metadata.drop_all(self.engine)
                # Manually drop the legacy version table which isn't in ORM metadata
                with self.engine.connect() as conn:
                    conn.execute(text("DROP TABLE IF EXISTS schema_version"))
                    conn.commit()
        except Exception as e:
            logger.warning(
                f"Error checking for legacy schema: {e}. Proceeding with creation."
            )

        # Create all tables defined in models.py
        Base.metadata.create_all(self.engine)

        # Micro-migration for v2.2.1: Add parent_id if missing
        try:
            from sqlalchemy import inspect

            inspector = inspect(self.engine)
            columns = [c["name"] for c in inspector.get_columns("focus_groups")]
            if "parent_id" not in columns:
                logger.info("Migrating schema: Adding parent_id to focus_groups")
                with self.engine.connect() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE focus_groups ADD COLUMN parent_id INTEGER REFERENCES focus_groups(id)"
                        )
                    )
                    conn.commit()
        except Exception as e:
            logger.warning(f"Schema migration check failed: {e}")

        # Micro-migration for v3.0: Add current_variant_id to transcripts
        try:
            from sqlalchemy import inspect

            inspector = inspect(self.engine)
            if "transcripts" in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns("transcripts")]
                if "current_variant_id" not in columns:
                    logger.info(
                        "Migrating schema: Adding current_variant_id to transcripts"
                    )
                    with self.engine.connect() as conn:
                        conn.execute(
                            text(
                                "ALTER TABLE transcripts ADD COLUMN current_variant_id INTEGER"
                            )
                        )
                        conn.commit()
        except Exception as e:
            logger.warning(f"Schema migration check for variants failed: {e}")

        # Enforce foreign keys (SQLite specific)
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))

    def _to_history_entry(self, transcript: Transcript) -> HistoryEntry:
        """Convert ORM model to DTO."""
        return HistoryEntry(
            timestamp=transcript.timestamp,
            text=transcript.normalized_text,
            duration_ms=transcript.duration_ms,
            speech_duration_ms=transcript.speech_duration_ms,
            focus_group_id=transcript.focus_group_id,
        )

    def add_entry(
        self, text: str, duration_ms: int = 0, speech_duration_ms: int = 0
    ) -> HistoryEntry:
        """
        Add new transcription to history.
        """
        timestamp = datetime.now().isoformat()

        try:
            with self.Session() as session:
                transcript = Transcript(
                    timestamp=timestamp,
                    raw_text=text,
                    normalized_text=text,
                    duration_ms=duration_ms,
                    speech_duration_ms=speech_duration_ms,
                )
                session.add(transcript)
                session.commit()
                # Refresh to get IDs etc if needed, but we have what we need for HistoryEntry

                # Check rotation
                self._rotate_if_needed(session)

                return self._to_history_entry(transcript)

        except Exception as e:
            logger.error(f"Failed to add history entry: {e}")
            # return a dummy entry to prevent crashes if DB fails
            return HistoryEntry(
                timestamp=timestamp,
                text=text,
                duration_ms=duration_ms,
                speech_duration_ms=speech_duration_ms,
            )

    def get_entry_by_timestamp(self, timestamp: str) -> HistoryEntry | None:
        """Get a single entry by its timestamp."""
        try:
            with self.Session() as session:
                stmt = select(Transcript).where(Transcript.timestamp == timestamp)
                transcript = session.execute(stmt).scalar_one_or_none()

                if transcript:
                    return self._to_history_entry(transcript)
                return None

        except Exception as e:
            logger.error(f"Failed to get entry by timestamp: {e}")
            return None

    def get_id_by_timestamp(self, timestamp: str) -> int | None:
        """Get the database ID for a given timestamp."""
        try:
            with self.Session() as session:
                stmt = select(Transcript.id).where(Transcript.timestamp == timestamp)
                return session.execute(stmt).scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get ID by timestamp: {e}")
            return None

    def get_transcript_variants(self, transcript_id: int) -> list[dict]:
        """Get all variants for a specific transcript."""
        try:
            with self.Session() as session:
                # Get current variant ID to flag active state and transcript context
                t_stmt = select(Transcript).where(Transcript.id == transcript_id)
                transcript = session.execute(t_stmt).scalar_one_or_none()

                if not transcript:
                    return []

                stmt = (
                    select(TranscriptVariant)
                    .where(TranscriptVariant.transcript_id == transcript_id)
                    .order_by(TranscriptVariant.created_at.asc())
                )
                variants = session.execute(stmt).scalars().all()

                results = []

                # Ensure we have a representation of the original (raw) text
                has_raw = any(v.kind == "raw" for v in variants)

                if not has_raw:
                    # Synthesize a raw variant from the base transcript
                    # It is current if no refinement is active (current_variant_id is None)
                    is_current = transcript.current_variant_id is None

                    results.append(
                        {
                            "id": 0,  # Synthetic ID for base transcript
                            "kind": "raw",
                            "text": transcript.raw_text,
                            "is_current": is_current,
                            "created_at": transcript.created_at,
                        }
                    )

                for v in variants:
                    results.append(
                        {
                            "id": v.id,
                            "kind": v.kind,
                            "text": v.text,
                            "is_current": (v.id == transcript.current_variant_id),
                            "created_at": v.created_at,
                        }
                    )
                return results
        except Exception as e:
            logger.error(f"Failed to get variants: {e}")
            return []

    def add_variant_atomic(
        self, transcript_id: int, text: str, kind: str, model_id: str | None = None
    ) -> bool:
        """
        Atomically add a new variant and update the transcript pointer.

        Args:
            transcript_id: ID of the transcript to update
            text: New text content
            kind: Variant kind ('raw', 'user_edit', 'refined')
            model_id: Optional ID of the model that generated this text

        Returns:
            bool: True if successful
        """
        try:
            with self.Session() as session:
                # 0. Check for exact duplicate (same kind, same text) to prevent spam
                stmt_dup = (
                    select(TranscriptVariant)
                    .where(
                        TranscriptVariant.transcript_id == transcript_id,
                        TranscriptVariant.kind == kind,
                        TranscriptVariant.text == text,
                    )
                    .limit(1)
                )
                existing_variant = session.execute(stmt_dup).scalar_one_or_none()

                if existing_variant:
                    logger.info(
                        f"Refusing to add duplicate variant {existing_variant.id} for transcript {transcript_id}"
                    )
                    # Update current pointer to this existing variant anyway
                    stmt_update = (
                        update(Transcript)
                        .where(Transcript.id == transcript_id)
                        .values(current_variant_id=existing_variant.id)
                    )
                    session.execute(stmt_update)
                    session.commit()
                    return True

                # 1. Enforce Refinement Limits (Delete oldest if > 3 exists)
                if kind == "refined":
                    stmt_count = (
                        select(TranscriptVariant.id)
                        .where(
                            TranscriptVariant.transcript_id == transcript_id,
                            TranscriptVariant.kind == "refined",
                        )
                        .order_by(TranscriptVariant.created_at.asc())
                    )

                    refined_ids = session.execute(stmt_count).scalars().all()

                    # Max 3 refined variants allowed. If adding 1, we must have at most 2 existing.
                    # So if len >= 3, delete (len - 2) oldest.
                    MAX_REFINEMENTS = 3
                    if len(refined_ids) >= MAX_REFINEMENTS:
                        ids_to_delete = refined_ids[
                            : len(refined_ids) - MAX_REFINEMENTS + 1
                        ]
                        if ids_to_delete:
                            logger.info(
                                f"Enforcing limit: deleting old refined variants {ids_to_delete}"
                            )
                            session.execute(
                                delete(TranscriptVariant).where(
                                    TranscriptVariant.id.in_(ids_to_delete)
                                )
                            )

                # 2. Create New Variant
                variant = TranscriptVariant(
                    transcript_id=transcript_id, text=text, kind=kind, model_id=model_id
                )
                session.add(variant)
                session.flush()  # Get ID

                # 3. Update Transcript Pointer
                stmt = (
                    update(Transcript)
                    .where(Transcript.id == transcript_id)
                    .values(
                        current_variant_id=variant.id,
                        normalized_text=text,  # Update legacy field for fallback
                    )
                )
                result = session.execute(stmt)

                if result.rowcount == 0:  # type: ignore[attr-defined]
                    logger.warning(
                        f"Transcript ID {transcript_id} not found during variant update"
                    )
                    session.rollback()
                    return False

                session.commit()
                logger.info(
                    f"Added variant {variant.id} ({kind}) to transcript {transcript_id}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to add variant: {e}")
            return False

    def get_recent(self, limit: int = HISTORY_RECENT_LIMIT) -> list[HistoryEntry]:
        """Get most recent entries (newest first)."""
        try:
            with self.Session() as session:
                stmt = select(Transcript).order_by(desc(Transcript.id)).limit(limit)
                transcripts = session.execute(stmt).scalars().all()

                return [self._to_history_entry(t) for t in transcripts]

        except Exception as e:
            logger.error(f"Failed to read history: {e}")
            return []

    def search(
        self,
        query: str,
        scope: str = "all",
        limit: int = 100,
    ) -> list[HistoryEntry]:
        """
        Search transcripts by text content.
        """
        if not query.strip():
            return []

        try:
            with self.Session() as session:
                stmt = select(Transcript).where(
                    Transcript.normalized_text.ilike(f"%{query}%")
                )

                match scope:
                    case "focus_groups":
                        stmt = stmt.where(Transcript.focus_group_id.is_not(None))
                    case "last_7_days":
                        cutoff = datetime.now() - timedelta(days=7)
                        stmt = stmt.where(Transcript.created_at >= cutoff)
                    case "last_30_days":
                        cutoff = datetime.now() - timedelta(days=30)
                        stmt = stmt.where(Transcript.created_at >= cutoff)
                    case _:
                        pass

                stmt = stmt.order_by(desc(Transcript.id)).limit(limit)
                transcripts = session.execute(stmt).scalars().all()

                return [self._to_history_entry(t) for t in transcripts]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def update_entry(self, timestamp: str, new_text: str) -> bool:
        """Update an existing entry's normalized_text by timestamp."""
        try:
            with self.Session() as session:
                stmt = (
                    update(Transcript)
                    .where(Transcript.timestamp == timestamp)
                    .values(normalized_text=new_text)
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:  # type: ignore[attr-defined]
                    logger.info(f"Updated history entry: {timestamp}")
                    return True
                else:
                    logger.warning(f"Entry not found for update: {timestamp}")
                    return False

        except Exception as e:
            logger.error(f"Failed to update history entry: {e}")
            return False

    def delete_entry(self, timestamp: str) -> bool:
        """Delete a history entry by timestamp."""
        try:
            with self.Session() as session:
                stmt = delete(Transcript).where(Transcript.timestamp == timestamp)
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:  # type: ignore[attr-defined]
                    logger.info(f"Deleted history entry: {timestamp}")
                    return True
                else:
                    logger.warning(f"Entry not found for deletion: {timestamp}")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete history entry: {e}")
            return False

    def clear(self) -> None:
        """Clear all history (delete all transcripts)."""
        try:
            with self.Session() as session:
                session.execute(delete(Transcript))
                session.commit()
                logger.info("History cleared")
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")

    def export_to_file(self, export_path: Path, format: str = "txt") -> bool:
        """Export history to file."""
        entries = self.get_recent(limit=HISTORY_EXPORT_LIMIT)

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

    def _rotate_if_needed(self, session: Session) -> None:
        """Remove oldest entries if exceeding limit."""
        max_entries = (
            ConfigManager.get_config_value("output_options", "max_history_entries")
            or 1000
        )
        if max_entries <= 0:
            return

        stmt_count = select(func.count(Transcript.id))
        count = session.execute(stmt_count).scalar() or 0

        if count > max_entries:
            to_remove = count - max_entries

            subq = select(Transcript.id).order_by(Transcript.id.asc()).limit(to_remove)
            delete_stmt = delete(Transcript).where(Transcript.id.in_(subq))

            session.execute(delete_stmt)
            session.commit()
            logger.info(f"Rotated history: removed {to_remove} old entries")

    # ========== Focus Group Methods ==========

    def create_focus_group(
        self, name: str, color: str | None = None, parent_id: int | None = None
    ) -> int | None:
        """Create a new focus group."""
        try:
            with self.Session() as session:
                group = FocusGroup(name=name, color=color, parent_id=parent_id)
                session.add(group)
                session.commit()
                return group.id

        except Exception as e:
            logger.error(f"Failed to create focus group: {e}")
            return None

    def get_focus_groups(self) -> list[tuple[int, str, str | None, int | None]]:
        """Get all focus groups."""
        try:
            with self.Session() as session:
                stmt = select(FocusGroup).order_by(FocusGroup.created_at.asc())
                groups = session.execute(stmt).scalars().all()
                return [(g.id, g.name, g.color, g.parent_id) for g in groups]

        except Exception as e:
            logger.error(f"Failed to get focus groups: {e}")
            return []

    def rename_focus_group(self, focus_group_id: int, new_name: str) -> bool:
        """Rename a focus group."""
        try:
            with self.Session() as session:
                stmt = (
                    update(FocusGroup)
                    .where(FocusGroup.id == focus_group_id)
                    .values(name=new_name)
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:  # type: ignore[attr-defined]
                    logger.info(f"Renamed focus group {focus_group_id} to '{new_name}'")
                    return True
                else:
                    logger.warning(f"Focus group {focus_group_id} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to rename focus group: {e}")
            return False

    def update_focus_group_color(self, focus_group_id: int, color: str | None) -> bool:
        """Update a focus group's accent color."""
        try:
            with self.Session() as session:
                stmt = (
                    update(FocusGroup)
                    .where(FocusGroup.id == focus_group_id)
                    .values(color=color)
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:  # type: ignore[attr-defined]
                    logger.info(
                        f"Updated focus group {focus_group_id} color to '{color}'"
                    )
                    return True
                else:
                    logger.warning(f"Focus group {focus_group_id} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to update focus group color: {e}")
            return False

    def delete_focus_group(
        self, focus_group_id: int, move_to_ungrouped: bool = True
    ) -> bool:
        """Delete a focus group."""
        try:
            with self.Session() as session:
                # Check if group has transcripts
                stmt_count = select(func.count(Transcript.id)).where(
                    Transcript.focus_group_id == focus_group_id
                )
                count = session.execute(stmt_count).scalar() or 0

                if count > 0 and not move_to_ungrouped:
                    logger.warning(
                        f"Cannot delete focus group {focus_group_id}: "
                        f"contains {count} transcripts"
                    )
                    return False

                if count > 0 and move_to_ungrouped:
                    update_stmt = (
                        update(Transcript)
                        .where(Transcript.focus_group_id == focus_group_id)
                        .values(focus_group_id=None)
                    )
                    session.execute(update_stmt)

                stmt = delete(FocusGroup).where(FocusGroup.id == focus_group_id)
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:  # type: ignore[attr-defined]
                    logger.info(f"Deleted focus group {focus_group_id}")
                    return True
                else:
                    logger.warning(f"Focus group {focus_group_id} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete focus group: {e}")
            return False

    def assign_transcript_to_focus_group(
        self, timestamp: str, focus_group_id: int | None
    ) -> bool:
        """Assign a transcript to a focus group."""
        try:
            with self.Session() as session:
                stmt = (
                    update(Transcript)
                    .where(Transcript.timestamp == timestamp)
                    .values(focus_group_id=focus_group_id)
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:  # type: ignore[attr-defined]
                    group_str = (
                        f"group {focus_group_id}" if focus_group_id else "ungrouped"
                    )
                    logger.info(f"Assigned transcript {timestamp} to {group_str}")
                    return True
                else:
                    logger.warning(f"Transcript {timestamp} not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to assign transcript to focus group: {e}")
            return False

    def get_transcripts_by_focus_group(
        self, focus_group_id: int | None, limit: int = 100
    ) -> list[HistoryEntry]:
        """Get transcripts belonging to a specific focus group."""
        try:
            with self.Session() as session:
                stmt = select(Transcript).where(
                    Transcript.focus_group_id == focus_group_id
                )
                stmt = stmt.order_by(desc(Transcript.id)).limit(limit)

                transcripts = session.execute(stmt).scalars().all()
                return [self._to_history_entry(t) for t in transcripts]

        except Exception as e:
            logger.error(f"Failed to get transcripts by focus group: {e}")
            return []

    def get_focus_group_counts(self) -> dict[int | None, int]:
        """Get transcript counts for all focus groups including ungrouped."""
        try:
            with self.Session() as session:
                stmt = select(
                    Transcript.focus_group_id, func.count(Transcript.id)
                ).group_by(Transcript.focus_group_id)
                results = session.execute(stmt).all()

                counts = {}
                for row in results:
                    counts[row[0]] = row[1]
                return counts

        except Exception as e:
            logger.error(f"Failed to get focus group counts: {e}")
            return {}

    def get_focus_group_colors(self) -> dict[int, str | None]:
        """Get color mapping for all focus groups."""
        try:
            with self.Session() as session:
                stmt = select(FocusGroup.id, FocusGroup.color)
                results = session.execute(stmt).all()

                colors = {}
                for row in results:
                    colors[row[0]] = row[1]
                return colors

        except Exception as e:
            logger.error(f"Failed to get focus group colors: {e}")
            return {}
