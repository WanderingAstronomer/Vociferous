# Data and Persistence

This page documents the database layer, ORM models, data transfer objects, and persistence patterns used in Vociferous.

---

## Overview

Vociferous uses **SQLAlchemy 2.0+** with SQLite for persistent storage of transcripts, projects, and configuration.

### Database Location

```
~/.config/vociferous/vociferous.db
```

### Key Files

| File | Purpose |
|------|---------|
| `src/database/models.py` | SQLAlchemy ORM models |
| `src/database/dtos.py` | Data Transfer Objects |
| `src/database/history_manager.py` | Repository facade |
| `src/database/signal_bridge.py` | Change notification |
| `src/database/events.py` | Event types |

---

## Database Schema

### Transcript

The primary entity representing a transcribed recording.

```python
class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_text: Mapped[str] = mapped_column(String, nullable=False)
    normalized_text: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    speech_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="transcripts")
    variants: Mapped[list["TranscriptVariant"]] = relationship(back_populates="transcript")
```

### Dual-Text Invariant

> **CRITICAL:** Each transcript maintains two distinct text representations:
> - **`raw_text`** — Immutable verbatim Whisper output. NEVER modified after creation.
> - **`normalized_text`** — Mutable user-facing text. May be edited, refined, or regenerated.

This separation preserves the original transcription while allowing user modifications.

### Project

Grouping for transcripts.

```python
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="project")
```

---

## Data Transfer Objects

DTOs are immutable, slotted dataclasses used for passing data to the UI layer.

### HistoryEntry

```python
@dataclass(slots=True)
class HistoryEntry:
    timestamp: str               # ISO 8601 String
    text: str                    # normalized_text for display
    duration_ms: int
    display_name: str | None
    speech_duration_ms: int
    project_id: int | None
    project_name: str | None
    id: int | None
```

---

## HistoryManager

The `HistoryManager` is the **repository facade** providing a clean API for all database operations.

### Location

`src/database/history_manager.py`

### Key Methods

| Method | Purpose |
|--------|---------|
| `add_transcript(raw_text, ...)` | Create new transcript |
| `get_entry(id)` | Retrieve single entry |
| `get_all_entries()` | List all entries |
| `update_normalized_text(id, text)` | Edit transcript |
| `delete_transcript(id)` | Remove transcript |
| `get_lifetime_metrics()` | Aggregate statistics |
| `export_to_csv(path)` | Export all data |

### Invariant

> **UI code MUST NOT execute raw SQL.** All database access goes through `HistoryManager`.

---

## Signal Bridge

The `DatabaseSignalBridge` provides real-time change notifications to UI components via PyQt signals.

### Location

`src/database/signal_bridge.py`

### EntityChange

```python
@dataclass
class EntityChange:
    entity_type: str          # "transcription", "project"
    action: ChangeAction      # CREATED, UPDATED, DELETED
    ids: list[int]            # Affected entity IDs
```
