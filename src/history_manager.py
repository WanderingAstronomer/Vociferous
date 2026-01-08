"""
Transcription history management with SQLite storage.

Replaces JSONL storage with structured database supporting:
- Immutable raw_text (audit baseline)
- Editable normalized_text (refinement target)
- Focus group membership (Phase 2)
- Efficient queries and updates
"""
import csv
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from utils import ConfigManager

logger = logging.getLogger(__name__)

# History database location
HISTORY_DIR = Path.home() / '.config' / 'vociferous'
HISTORY_DB = HISTORY_DIR / 'vociferous.db'

# Schema version for future migrations
SCHEMA_VERSION = 1


@dataclass(slots=True)
class HistoryEntry:
    """Single transcription history entry with timestamp, text, and duration."""
    timestamp: str
    text: str
    duration_ms: int

    def to_display_string(self, max_length: int = 80) -> str:
        """Format for display in list widget: [HH:MM:SS] text preview..."""
        timestamp_short = self.timestamp.split('T')[1][:8]  # HH:MM:SS
        if len(self.text) > max_length:
            text_preview = self.text[:max_length] + '...'
        else:
            text_preview = self.text
        return f"[{timestamp_short}] {text_preview}"


class HistoryManager:
    """
    Manages transcription history with SQLite storage.

    Maintains API compatibility with JSONL-based implementation while
    providing efficient updates, deletes, and queries.

    Schema enforces:
    - raw_text immutability (never updated after creation)
    - normalized_text editability (target for refinement/edits)
    """

    def __init__(self, history_file: Path | None = None) -> None:
        """Initialize history manager with optional custom database path."""
        self.history_file = history_file or HISTORY_DB
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema and versioning."""
        with sqlite3.connect(self.history_file) as conn:
            conn.execute('PRAGMA foreign_keys = ON')

            # Schema versioning table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Focus groups (Phase 2, created now to avoid ALTER later)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS focus_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Transcripts table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    raw_text TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    duration_ms INTEGER DEFAULT 0,
                    focus_group_id INTEGER,
                    FOREIGN KEY (focus_group_id) REFERENCES focus_groups(id) ON DELETE SET NULL
                )
            ''')

            # Indexes for efficient queries
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_transcripts_created
                ON transcripts(created_at DESC)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp
                ON transcripts(timestamp)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_transcripts_focus
                ON transcripts(focus_group_id)
            ''')

            # Record schema version
            conn.execute('''
                INSERT OR IGNORE INTO schema_version (version) VALUES (?)
            ''', (SCHEMA_VERSION,))

            conn.commit()

    def add_entry(self, text: str, duration_ms: int = 0) -> HistoryEntry:
        """
        Add new transcription to history. Returns the created entry.

        Sets both raw_text and normalized_text to the same initial value.
        raw_text will never be modified after this point.
        """
        timestamp = datetime.now().isoformat()

        try:
            with sqlite3.connect(self.history_file) as conn:
                conn.execute('''
                    INSERT INTO transcripts (timestamp, raw_text, normalized_text, duration_ms)
                    VALUES (?, ?, ?, ?)
                ''', (timestamp, text, text, duration_ms))

                conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Failed to add history entry: {e}")

        # Check if rotation needed
        max_entries = ConfigManager.get_config_value(
            'output_options', 'max_history_entries'
        ) or 1000
        if max_entries > 0:
            self._rotate_if_needed(max_entries)

        return HistoryEntry(
            timestamp=timestamp,
            text=text,
            duration_ms=duration_ms
        )

    def get_recent(self, limit: int = 100) -> list[HistoryEntry]:
        """Get most recent entries (newest first)."""
        try:
            with sqlite3.connect(self.history_file) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT timestamp, normalized_text, duration_ms
                    FROM transcripts
                    ORDER BY id DESC
                    LIMIT ?
                ''', (limit,))

                entries = []
                for row in cursor:
                    entries.append(HistoryEntry(
                        timestamp=row['timestamp'],
                        text=row['normalized_text'],  # Return editable version
                        duration_ms=row['duration_ms']
                    ))

                return entries

        except sqlite3.Error as e:
            logger.error(f"Failed to read history: {e}")
            return []

    def update_entry(self, timestamp: str, new_text: str) -> bool:
        """
        Update an existing entry's normalized_text by timestamp.

        raw_text is NEVER modified to maintain audit baseline.
        Returns success status.
        """
        try:
            with sqlite3.connect(self.history_file) as conn:
                cursor = conn.execute('''
                    UPDATE transcripts
                    SET normalized_text = ?
                    WHERE timestamp = ?
                ''', (new_text, timestamp))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Updated history entry: {timestamp}")
                    return True
                else:
                    logger.warning(f"Entry not found for update: {timestamp}")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Failed to update history entry: {e}")
            return False

    def delete_entry(self, timestamp: str) -> bool:
        """Delete a history entry by timestamp."""
        try:
            with sqlite3.connect(self.history_file) as conn:
                cursor = conn.execute('''
                    DELETE FROM transcripts
                    WHERE timestamp = ?
                ''', (timestamp,))

                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Deleted history entry: {timestamp}")
                    return True
                else:
                    logger.warning(f"Entry not found for deletion: {timestamp}")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Failed to delete history entry: {e}")
            return False

    def clear(self) -> None:
        """Clear all history (delete all transcripts)."""
        try:
            with sqlite3.connect(self.history_file) as conn:
                conn.execute('DELETE FROM transcripts')
                conn.commit()
                logger.info("History cleared")
        except sqlite3.Error as e:
            logger.error(f"Failed to clear history: {e}")

    def export_to_file(self, export_path: Path, format: str = 'txt') -> bool:
        """Export history to file (txt, csv, or md format)."""
        entries = self.get_recent(limit=10000)  # Export all

        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                match format:
                    case 'txt':
                        for entry in entries:
                            f.write(f"[{entry.timestamp}]\n{entry.text}\n\n")

                    case 'csv':
                        writer = csv.writer(f)
                        writer.writerow(['Timestamp', 'Text', 'Duration (ms)'])
                        for entry in entries:
                            writer.writerow([
                                entry.timestamp,
                                entry.text,
                                entry.duration_ms
                            ])

                    case 'md':
                        f.write("# Vociferous Transcription History\n\n")
                        current_day = None
                        for entry in entries:
                            # Parse timestamp for grouping by day
                            dt = datetime.fromisoformat(entry.timestamp)
                            day_key = dt.date().isoformat()
                            
                            # New day header
                            if current_day != day_key:
                                current_day = day_key
                                # Format: "December 13th, 2025"
                                month = dt.strftime("%B")
                                day = dt.day
                                suffix = self._ordinal_suffix(day)
                                year = dt.year
                                f.write(f"## {month} {day}{suffix}, {year}\n\n")
                            
                            # Time header: "10:03 p.m."
                            time_str = dt.strftime("%I:%M %p")
                            time_str = time_str.replace("AM", "a.m.").replace("PM", "p.m.")
                            if time_str.startswith("0"):
                                time_str = time_str[1:]
                            f.write(f"### {time_str}\n\n")
                            
                            # Content
                            f.write(f"{entry.text}\n\n")
                            
                            # Duration as italicized note
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

    def _rotate_if_needed(self, max_entries: int) -> None:
        """Remove oldest entries if exceeding limit."""
        try:
            with sqlite3.connect(self.history_file) as conn:
                # Count current entries
                cursor = conn.execute('SELECT COUNT(*) FROM transcripts')
                count = cursor.fetchone()[0]

                if count > max_entries:
                    # Delete oldest entries (lowest IDs)
                    conn.execute('''
                        DELETE FROM transcripts
                        WHERE id IN (
                            SELECT id FROM transcripts
                            ORDER BY id ASC
                            LIMIT ?
                        )
                    ''', (count - max_entries,))

                    conn.commit()
                    removed = count - max_entries
                    logger.info(f"Rotated history: removed {removed} old entries")

        except sqlite3.Error as e:
            logger.warning(f"History rotation failed: {e}")

    def _ordinal_suffix(self, n: int) -> str:
        """Return ordinal suffix (st/nd/rd/th)."""
        if 11 <= (n % 100) <= 13:
            return "th"
        match n % 10:
            case 1:
                return "st"
            case 2:
                return "nd"
            case 3:
                return "rd"
            case _:
                return "th"

    # ========== Focus Group Methods (Phase 2) ==========

    def create_focus_group(self, name: str) -> int | None:
        """
        Create a new focus group.

        Args:
            name: Display name for the focus group

        Returns:
            Focus group ID on success, None on failure
        """
        try:
            with sqlite3.connect(self.history_file) as conn:
                cursor = conn.execute('''
                    INSERT INTO focus_groups (name)
                    VALUES (?)
                ''', (name,))
                conn.commit()
                return cursor.lastrowid

        except sqlite3.Error as e:
            logger.error(f"Failed to create focus group: {e}")
            return None

    def get_focus_groups(self) -> list[tuple[int, str]]:
        """
        Get all focus groups.

        Returns:
            List of (id, name) tuples ordered by creation date
        """
        try:
            with sqlite3.connect(self.history_file) as conn:
                cursor = conn.execute('''
                    SELECT id, name
                    FROM focus_groups
                    ORDER BY created_at ASC
                ''')
                return cursor.fetchall()

        except sqlite3.Error as e:
            logger.error(f"Failed to get focus groups: {e}")
            return []

    def rename_focus_group(self, focus_group_id: int, new_name: str) -> bool:
        """
        Rename a focus group.

        Args:
            focus_group_id: ID of the focus group to rename
            new_name: New display name

        Returns:
            True on success, False on failure
        """
        try:
            with sqlite3.connect(self.history_file) as conn:
                cursor = conn.execute('''
                    UPDATE focus_groups
                    SET name = ?
                    WHERE id = ?
                ''', (new_name, focus_group_id))
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Renamed focus group {focus_group_id} to '{new_name}'")
                    return True
                else:
                    logger.warning(f"Focus group {focus_group_id} not found")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Failed to rename focus group: {e}")
            return False

    def delete_focus_group(self, focus_group_id: int, move_to_ungrouped: bool = True) -> bool:
        """
        Delete a focus group.

        Args:
            focus_group_id: ID of the focus group to delete
            move_to_ungrouped: If True, move transcripts to ungrouped (NULL).
                             If False, block deletion if group has transcripts.

        Returns:
            True on success, False on failure
        """
        try:
            with sqlite3.connect(self.history_file) as conn:
                conn.execute('PRAGMA foreign_keys = ON')  # Enable FK for this connection
                
                # Check if group has transcripts
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM transcripts
                    WHERE focus_group_id = ?
                ''', (focus_group_id,))
                count = cursor.fetchone()[0]

                if count > 0 and not move_to_ungrouped:
                    logger.warning(
                        f"Cannot delete focus group {focus_group_id}: "
                        f"contains {count} transcripts"
                    )
                    return False

                # Delete the group (foreign key ON DELETE SET NULL handles transcripts)
                cursor = conn.execute('''
                    DELETE FROM focus_groups
                    WHERE id = ?
                ''', (focus_group_id,))
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Deleted focus group {focus_group_id}")
                    return True
                else:
                    logger.warning(f"Focus group {focus_group_id} not found")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Failed to delete focus group: {e}")
            return False

    def assign_transcript_to_focus_group(
        self, timestamp: str, focus_group_id: int | None
    ) -> bool:
        """
        Assign a transcript to a focus group (or ungrouped if None).

        Args:
            timestamp: Timestamp of the transcript to update
            focus_group_id: Focus group ID, or None for ungrouped

        Returns:
            True on success, False on failure
        """
        try:
            with sqlite3.connect(self.history_file) as conn:
                cursor = conn.execute('''
                    UPDATE transcripts
                    SET focus_group_id = ?
                    WHERE timestamp = ?
                ''', (focus_group_id, timestamp))
                conn.commit()

                if cursor.rowcount > 0:
                    group_str = f"group {focus_group_id}" if focus_group_id else "ungrouped"
                    logger.info(f"Assigned transcript {timestamp} to {group_str}")
                    return True
                else:
                    logger.warning(f"Transcript {timestamp} not found")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Failed to assign transcript to focus group: {e}")
            return False

    def get_transcripts_by_focus_group(
        self, focus_group_id: int | None, limit: int = 100
    ) -> list[HistoryEntry]:
        """
        Get transcripts belonging to a specific focus group (or ungrouped).

        Args:
            focus_group_id: Focus group ID, or None for ungrouped transcripts
            limit: Maximum number of entries to return

        Returns:
            List of HistoryEntry objects (newest first)
        """
        try:
            with sqlite3.connect(self.history_file) as conn:
                conn.row_factory = sqlite3.Row

                if focus_group_id is None:
                    # Get ungrouped transcripts
                    cursor = conn.execute('''
                        SELECT timestamp, normalized_text, duration_ms
                        FROM transcripts
                        WHERE focus_group_id IS NULL
                        ORDER BY id DESC
                        LIMIT ?
                    ''', (limit,))
                else:
                    # Get transcripts for specific group
                    cursor = conn.execute('''
                        SELECT timestamp, normalized_text, duration_ms
                        FROM transcripts
                        WHERE focus_group_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                    ''', (focus_group_id, limit))

                entries = []
                for row in cursor:
                    entries.append(HistoryEntry(
                        timestamp=row['timestamp'],
                        text=row['normalized_text'],
                        duration_ms=row['duration_ms']
                    ))

                return entries

        except sqlite3.Error as e:
            logger.error(f"Failed to get transcripts by focus group: {e}")
            return []
