"""
SQLAlchemy models for Vociferous history database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class FocusGroup(Base):
    """
    Represents a grouping of transcripts.
    """

    __tablename__ = "focus_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Hierarchical Relationship
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("focus_groups.id"), nullable=True
    )

    # Self-referential accessors
    children: Mapped[list["FocusGroup"]] = relationship(
        "FocusGroup", back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped["FocusGroup | None"] = relationship(
        "FocusGroup", back_populates="children", remote_side=[id]
    )

    transcripts: Mapped[list["Transcript"]] = relationship(
        back_populates="focus_group", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FocusGroup(id={self.id}, name='{self.name}')>"


class TranscriptVariant(Base):
    """
    Represents a version of the transcript text (raw, edited, or refined).
    Ensures non-destructive history.
    """

    __tablename__ = "transcript_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transcript_id: Mapped[int] = mapped_column(
        ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        String, nullable=False
    )  # 'raw', 'user_edit', 'refined'
    text: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Backref from Transcript (defined loosely to avoid circular dependency issues at import time if strictly typed)
    # But usually defined in valid SQLAlchemy 2.0 style.


class Transcript(Base):
    """
    Represents a single audio transcription.

    Attributes:
        raw_text: Immutable original transcription
        normalized_text: Mutable text for user edits (Storage for legacy/fallback)
        duration_ms: Total audio processing time
        speech_duration_ms: Time containing speech (VAD)
        current_variant_id: Pointer to the active text version
    """

    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    raw_text: Mapped[str] = mapped_column(String, nullable=False)
    normalized_text: Mapped[str] = mapped_column(String, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    speech_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    focus_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("focus_groups.id"), nullable=True, index=True
    )
    current_variant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("transcript_variants.id"), nullable=True
    )

    focus_group: Mapped[Optional[FocusGroup]] = relationship(
        back_populates="transcripts"
    )

    current_variant: Mapped[Optional[TranscriptVariant]] = relationship(
        foreign_keys=[current_variant_id], post_update=True
    )

    variants: Mapped[list[TranscriptVariant]] = relationship(
        foreign_keys=[TranscriptVariant.transcript_id],
        backref="transcript",
        cascade="all, delete-orphan",
    )

    @property
    def text(self) -> str:
        """Alias for current variant text or normalized_text (legacy fallback)."""
        if self.current_variant:
            return self.current_variant.text
        return self.normalized_text

    @text.setter
    def text(self, value: str) -> None:
        # Note: Setters on hybrid properties or proxies can be tricky.
        # For now, we update normalized_text as fallback, but the HistoryManager
        # should prefer creating variants.
        self.normalized_text = value

    def to_display_string(self, max_length: int = 80) -> str:
        """Format for display in list widget: [HH:MM:SS] text preview..."""
        # Timestamp expected format: YYYY-MM-DDTHH:MM:SS.mmmmmm
        try:
            timestamp_short = self.timestamp.split("T")[1][:8]
        except IndexError:
            timestamp_short = self.timestamp[-8:]

        current_text = self.normalized_text
        if len(current_text) > max_length:
            text_preview = current_text[:max_length] + "..."
        else:
            text_preview = current_text
        return f"[{timestamp_short}] {text_preview}"

    def __repr__(self) -> str:
        return f"<Transcript(id={self.id}, timestamp='{self.timestamp}')>"
