# History Storage

Transcription history is persisted using SQLite database with **SQLAlchemy** ORM.

## File Location

```
~/.config/vociferous/vociferous.db
```

Created automatically on first start.

## Database Architecture (SQLAlchemy)

The system uses SQLAlchemy 2.0+ ORM with declarative models defined in `src/models.py`.

###  `transcripts` Table (Transcript Model)

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER | Auto-increment primary key |
| `timestamp` | TEXT | ISO-8601 format with microseconds (Unique Index, Business Key) |
| `created_at` | DATETIME | Insertion timestamp (Indexed) |
| `raw_text` | TEXT | Original Whisper output (immutable) |
| `normalized_text` | TEXT | Editable user content |
| `duration_ms` | INTEGER | Recording duration in milliseconds |
| `speech_duration_ms` | INTEGER | VAD-filtered speech time |
| `focus_group_id` | INTEGER | Foreign key to `focus_groups.id` (Indexed) |

### `focus_groups` Table (FocusGroup Model)

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER | Auto-increment primary key |
| `name` | TEXT | User-defined group name |
| `color` | TEXT | Hex color code (e.g. #FF0000) or null |
| `created_at` | DATETIME | Creation timestamp |

## Dual-Text Architecture

Each transcript stores two versions of the text:

- **`raw_text`**: Immutable. The exact output from Whisper. Never modified.
- **`normalized_text`**: Editable. Target for user edits and future refinement.

Both are initialized to identical values on creation.

## Technology Stack

- **Engine**: SQLite (via `sqlite3` driver)
- **ORM**: SQLAlchemy (Declarative mapping)
- **Migrations**: Automatic schema creation on startup. Legacy schemas are replaced ("nuked") to ensure consistency with current models.

## Usage

### Add Transcript

```python
# Internal Transcript model is created and persisted via Session
manager.add_entry(
    text="Transcribed text",
    duration_ms=2500,
    speech_duration_ms=2100
)
```

### Read Recent

```python
# Leverages ORM lazy loading (though specific query is eager for list views)
entries = manager.get_recent(limit=100)  # Returns HistoryEntry DTOs
```

### Operations

Standard CRUD operations are performed via SQLAlchemy `Session` context managers ensuring ACID compliance.

## Focus Groups

Organize transcripts by topic or project. The `FocusGroup` model supports hierarchical relationships (prepared for future implementation).

```python
# Create group
group_id = manager.create_focus_group("Work Notes", color="#FF0000")
```
