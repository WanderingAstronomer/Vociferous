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

    transcripts: Mapped[list["Transcript"]] = relationship(
        back_populates="focus_group", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<FocusGroup(id={self.id}, name='{self.name}')>"


class Transcript(Base):
    """
    Represents a single audio transcription.
    
    Attributes:
        raw_text: Immutable original transcription
        normalized_text: Mutable text for user edits
        duration_ms: Total audio processing time
        speech_duration_ms: Time containing speech (VAD)
    """
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    raw_text: Mapped[str] = mapped_column(String, nullable=False)
    normalized_text: Mapped[str] = mapped_column(String, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    speech_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    focus_group_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("focus_groups.id"), nullable=True, index=True
    )

    focus_group: Mapped[Optional[FocusGroup]] = relationship(back_populates="transcripts")

    @property
    def text(self) -> str:
        """Alias for normalized_text to match legacy interface."""
        return self.normalized_text
    
    @text.setter
    def text(self, value: str) -> None:
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
