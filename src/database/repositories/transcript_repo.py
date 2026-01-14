import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, desc, func, select, update

from database.core import DatabaseCore
from database.dtos import HistoryEntry
from database.models import Transcript, TranscriptVariant
from utils import ConfigManager

logger = logging.getLogger(__name__)

class TranscriptRepository:
    def __init__(self, db_core: DatabaseCore):
        self.db = db_core

    def _to_history_entry(self, transcript: Transcript) -> HistoryEntry:
        """Helper to convert DB model to DTO."""
        return HistoryEntry(
            timestamp=transcript.timestamp,
            text=transcript.normalized_text,  # The current visible text
            duration_ms=transcript.duration_ms,
            speech_duration_ms=transcript.speech_duration_ms,
            focus_group_id=transcript.focus_group_id,
            id=transcript.id,
        )

    def add_entry(
        self, text: str, duration_ms: int = 0, speech_duration_ms: int = 0
    ) -> HistoryEntry:
        """
        Add new transcription to history.
        """
        timestamp = datetime.now().isoformat()

        try:
            with self.db.get_session() as session:
                transcript = Transcript(
                    timestamp=timestamp,
                    raw_text=text,
                    normalized_text=text,
                    duration_ms=duration_ms,
                    speech_duration_ms=speech_duration_ms,
                )
                session.add(transcript)
                session.commit()
                
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
            with self.db.get_session() as session:
                stmt = select(Transcript).where(Transcript.timestamp == timestamp)
                transcript = session.execute(stmt).scalar_one_or_none()

                if transcript:
                    return self._to_history_entry(transcript)
                return None

        except Exception as e:
            logger.error(f"Failed to get entry by timestamp: {e}")
            return None

    def get_entry(self, transcript_id: int) -> HistoryEntry | None:
        """Get a single entry by its ID."""
        try:
            with self.db.get_session() as session:
                transcript = session.get(Transcript, transcript_id)
                if transcript:
                    return self._to_history_entry(transcript)
                return None
        except Exception as e:
            logger.error(f"Failed to get entry by ID: {e}")
            return None

    def get_id_by_timestamp(self, timestamp: str) -> int | None:
        """Get the database ID for a given timestamp."""
        try:
            with self.db.get_session() as session:
                stmt = select(Transcript.id).where(Transcript.timestamp == timestamp)
                return session.execute(stmt).scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get ID by timestamp: {e}")
            return None

    def get_transcript_variants(self, transcript_id: int) -> list[dict]:
        """Get all variants for a specific transcript."""
        try:
            with self.db.get_session() as session:
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
                    is_current = transcript.current_variant_id is None
                    results.append(
                        {
                            "id": 0,
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
        """Atomically add a new variant and update the transcript pointer."""
        try:
            with self.db.get_session() as session:
                # 0. Check for exact duplicate
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
                    stmt_update = (
                        update(Transcript)
                        .where(Transcript.id == transcript_id)
                        .values(current_variant_id=existing_variant.id)
                    )
                    session.execute(stmt_update)
                    session.commit()
                    return True

                # 1. Enforce Refinement Limits
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

                    MAX_REFINEMENTS = 3
                    if len(refined_ids) >= MAX_REFINEMENTS:
                        ids_to_delete = refined_ids[: len(refined_ids) - MAX_REFINEMENTS + 1]
                        if ids_to_delete:
                            logger.info(f"Enforcing limit: deleting old refined variants {ids_to_delete}")
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
                session.flush()

                # 3. Update Transcript Pointer
                stmt = (
                    update(Transcript)
                    .where(Transcript.id == transcript_id)
                    .values(
                        current_variant_id=variant.id,
                        normalized_text=text,
                    )
                )
                result = session.execute(stmt)

                if result.rowcount == 0:
                    logger.warning(f"Transcript ID {transcript_id} not found during variant update")
                    session.rollback()
                    return False

                session.commit()
                logger.info(f"Added variant {variant.id} ({kind}) to transcript {transcript_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to add variant: {e}")
            return False

    def get_recent(self, limit: int = 100) -> list[HistoryEntry]:
        """Get most recent entries (newest first)."""
        try:
            with self.db.get_session() as session:
                stmt = select(Transcript).order_by(desc(Transcript.id)).limit(limit)
                transcripts = session.execute(stmt).scalars().all()
                return [self._to_history_entry(t) for t in transcripts]

        except Exception as e:
            logger.error(f"Failed to read history: {e}")
            return []

    def search(self, query: str, scope: str = "all", limit: int = 100) -> list[HistoryEntry]:
        """Search transcripts by text content."""
        if not query.strip():
            return []

        try:
            with self.db.get_session() as session:
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
            with self.db.get_session() as session:
                stmt = (
                    update(Transcript)
                    .where(Transcript.timestamp == timestamp)
                    .values(normalized_text=new_text)
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:
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
            with self.db.get_session() as session:
                stmt = delete(Transcript).where(Transcript.timestamp == timestamp)
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:
                    logger.info(f"Deleted history entry: {timestamp}")
                    return True
                else:
                    logger.warning(f"Entry not found for deletion: {timestamp}")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete history entry: {e}")
            return False

    def clear(self) -> None:
        """Clear all history."""
        try:
            with self.db.get_session() as session:
                session.execute(delete(Transcript))
                session.commit()
                logger.info("History cleared")
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")

    def _rotate_if_needed(self, session) -> None:
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

    def assign_to_focus_group(
        self, timestamp: str, focus_group_id: int | None
    ) -> bool:
        """Assign a transcript to a focus group."""
        try:
            with self.db.get_session() as session:
                stmt = (
                    update(Transcript)
                    .where(Transcript.timestamp == timestamp)
                    .values(focus_group_id=focus_group_id)
                )
                result = session.execute(stmt)
                session.commit()

                if result.rowcount > 0:
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

    def get_by_focus_group(
        self, focus_group_id: int | None, limit: int = 100
    ) -> list[HistoryEntry]:
        """Get transcripts belonging to a specific focus group."""
        try:
            with self.db.get_session() as session:
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
            with self.db.get_session() as session:
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
