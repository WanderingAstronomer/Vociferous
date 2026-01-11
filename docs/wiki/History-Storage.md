# History Storage

Transcription history is persisted using SQLite database.

## File Location

```
~/.config/vociferous/vociferous.db
```

Created automatically on first transcription.

## Database Schema

### transcripts table

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER | Auto-increment primary key |
| `timestamp` | TEXT | ISO-8601 format with microseconds |
| `raw_text` | TEXT | Original Whisper output (immutable) |
| `normalized_text` | TEXT | Editable user content |
| `duration_ms` | INTEGER | Recording duration in milliseconds |
| `speech_duration_ms` | INTEGER | VAD-filtered speech time |
| `focus_group_id` | INTEGER | Foreign key to focus_groups (nullable) |
| `created_at` | TEXT | Creation timestamp |

### focus_groups table

| Column | Type | Description |
| --- | --- | --- |
| `id` | INTEGER | Auto-increment primary key |
| `name` | TEXT | User-defined group name |
| `created_at` | TEXT | Creation timestamp |

## Dual-Text Architecture

Each transcript stores two versions of the text:

- **`raw_text`**: Immutable. The exact output from Whisper. Never modified.
- **`normalized_text`**: Editable. Target for user edits and future refinement.

Both are initialized to identical values on creation.

## Why SQLite?

- **ACID transactions**: Reliable updates and deletes
- **Indexes**: Fast queries by id, timestamp, focus_group_id
- **Foreign keys**: Referential integrity for focus groups
- **Rich queries**: Filter by focus group, full-text search
- **Single file**: Easy backup and portability

## Operations

### Add Transcript

```python
manager.add_entry(
    raw_text="Transcribed text",
    normalized_text="Transcribed text",
    duration_ms=2500,
    speech_duration_ms=2100
)
```

### Read Recent

```python
entries = manager.get_entries(limit=100)  # Returns newest first
```

### Update Entry

```python
manager.update_entry(timestamp, new_text="Edited text")
# Only normalized_text is modified; raw_text is preserved
```

### Delete Entry

```python
manager.delete_entry(timestamp)
```

## Focus Groups

Organize transcripts by topic or project:

```python
# Create group
group_id = manager.create_focus_group("Work Notes")

# Assign transcript
manager.assign_transcript_to_focus_group(timestamp, group_id)

# Filter by group
entries = manager.get_transcripts_by_focus_group(group_id)

# Ungroup (move to ungrouped)
manager.assign_transcript_to_focus_group(timestamp, None)

# Delete group (transcripts become ungrouped via ON DELETE SET NULL)
manager.delete_focus_group(group_id)
```

## Rotation

When entries exceed `max_history_entries` (default 1000), oldest entries are removed:

```python
# Automatic rotation after each write
# Deletes by id ASC (oldest entries)
```

## Export Formats

### Plain Text (.txt)

```
[2025-01-15T10:30:45]
Hello world

[2025-01-15T10:31:12]
Another transcription
```

### CSV

```csv
Timestamp,Text,Duration (ms)
2025-01-15T10:30:45,Hello world,2500
2025-01-15T10:31:12,Another transcription,1800
```

### Markdown

```markdown
# Vociferous Transcription History

## January 15th, 2025

### 10:30 a.m.

Hello world

*Duration: 2500ms*

---
```

## Metrics Data

Each transcript stores timing data for the metrics framework:

- **`duration_ms`**: Total recording time (human cognitive time)
- **`speech_duration_ms`**: VAD-filtered speech segments (machine processing time)
- **Silence time**: Calculated as `duration_ms - speech_duration_ms`

## Configuration

```yaml
output_options:
  max_history_entries: 1000  # 0 = unlimited
```
    def from_json(cls, json_str: str) -> 'HistoryEntry': ...
```

Uses `slots=True` for memory efficiency with many entries.