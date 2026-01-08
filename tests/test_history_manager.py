"""
Tests for SQLite-based HistoryManager.

Validates:
- Database initialization and schema
- CRUD operations (add, get, update, delete)
- raw_text immutability
- normalized_text editability
- Export functionality
- Rotation behavior
"""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from history_manager import HistoryEntry, HistoryManager


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    # Remove the created file so tests can verify creation
    db_path.unlink()
    yield db_path
    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def history_manager(temp_db):
    """Create a HistoryManager with temporary database, cleared before each test."""
    hm = HistoryManager(history_file=temp_db)
    hm.clear()  # Ensure clean state for each test
    return hm


class TestDatabaseInitialization:
    """Test database schema creation and versioning."""

    def test_creates_database_file(self, temp_db):
        """Database file should be created on initialization."""
        assert not temp_db.exists()
        HistoryManager(history_file=temp_db)
        assert temp_db.exists()

    def test_creates_required_tables(self, history_manager, temp_db):
        """Should create transcripts, focus_groups, and schema_version tables."""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = {row[0] for row in cursor}

        assert 'transcripts' in tables
        assert 'focus_groups' in tables
        assert 'schema_version' in tables

    def test_transcripts_schema(self, history_manager, temp_db):
        """Transcripts table should have correct columns."""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute('PRAGMA table_info(transcripts)')
            columns = {row[1]: row[2] for row in cursor}

        assert 'id' in columns
        assert 'timestamp' in columns
        assert 'created_at' in columns
        assert 'raw_text' in columns
        assert 'normalized_text' in columns
        assert 'duration_ms' in columns
        assert 'focus_group_id' in columns

    def test_creates_indexes(self, history_manager, temp_db):
        """Should create indexes for efficient queries."""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            indexes = {row[0] for row in cursor}

        assert 'idx_transcripts_created' in indexes
        assert 'idx_transcripts_timestamp' in indexes
        assert 'idx_transcripts_focus' in indexes

    def test_foreign_key_constraint(self, history_manager, temp_db):
        """Should have foreign key from transcripts to focus_groups."""
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute('PRAGMA foreign_key_list(transcripts)')
            fks = cursor.fetchall()

        assert len(fks) == 1
        assert fks[0][2] == 'focus_groups'  # Referenced table


class TestAddEntry:
    """Test adding transcription entries."""

    def test_add_entry_returns_history_entry(self, history_manager):
        """add_entry should return a HistoryEntry with timestamp."""
        entry = history_manager.add_entry('Test text', 1000)

        assert isinstance(entry, HistoryEntry)
        assert entry.text == 'Test text'
        assert entry.duration_ms == 1000
        assert entry.timestamp  # Should have ISO timestamp

    def test_add_entry_persists_to_database(self, history_manager, temp_db):
        """Entry should be stored in database."""
        entry = history_manager.add_entry('Persisted text', 500)

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                'SELECT raw_text, normalized_text, duration_ms FROM transcripts '
                'WHERE timestamp = ?',
                (entry.timestamp,)
            )
            row = cursor.fetchone()

        assert row is not None
        assert row[0] == 'Persisted text'  # raw_text
        assert row[1] == 'Persisted text'  # normalized_text (same initially)
        assert row[2] == 500

    def test_raw_and_normalized_text_identical_on_creation(self, history_manager, temp_db):
        """Both raw_text and normalized_text should be set to same value."""
        entry = history_manager.add_entry('Initial text')

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                'SELECT raw_text, normalized_text FROM transcripts WHERE timestamp = ?',
                (entry.timestamp,)
            )
            raw, normalized = cursor.fetchone()

        assert raw == normalized == 'Initial text'


class TestGetRecent:
    """Test retrieving recent entries."""

    def test_get_recent_empty_database(self, history_manager):
        """Should return empty list for empty database."""
        entries = history_manager.get_recent()
        assert entries == []

    def test_get_recent_returns_newest_first(self, history_manager):
        """Entries should be ordered newest first."""
        history_manager.add_entry('First', 100)
        history_manager.add_entry('Second', 200)
        history_manager.add_entry('Third', 300)

        entries = history_manager.get_recent()

        assert len(entries) >= 3
        # Check last 3 entries (might have leftover from previous tests)
        assert entries[0].text == 'Third'
        assert entries[1].text == 'Second'
        assert entries[2].text == 'First'

    def test_get_recent_respects_limit(self, history_manager):
        """Should respect the limit parameter."""
        for i in range(10):
            history_manager.add_entry(f'Entry {i}')

        entries = history_manager.get_recent(limit=3)
        assert len(entries) == 3

    def test_get_recent_returns_normalized_text(self, history_manager, temp_db):
        """Should return normalized_text, not raw_text."""
        entry = history_manager.add_entry('Original')

        # Update normalized_text directly in DB
        with sqlite3.connect(temp_db) as conn:
            conn.execute(
                'UPDATE transcripts SET normalized_text = ? WHERE timestamp = ?',
                ('Modified', entry.timestamp)
            )
            conn.commit()

        entries = history_manager.get_recent(1)
        assert entries[0].text == 'Modified'


class TestUpdateEntry:
    """Test updating entry normalized_text."""

    def test_update_entry_modifies_normalized_text(self, history_manager, temp_db):
        """Should update normalized_text in database."""
        entry = history_manager.add_entry('Original text')
        success = history_manager.update_entry(entry.timestamp, 'Updated text')

        assert success is True

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                'SELECT normalized_text FROM transcripts WHERE timestamp = ?',
                (entry.timestamp,)
            )
            normalized = cursor.fetchone()[0]

        assert normalized == 'Updated text'

    def test_update_entry_preserves_raw_text(self, history_manager, temp_db):
        """raw_text should NEVER be modified."""
        entry = history_manager.add_entry('Original text')
        history_manager.update_entry(entry.timestamp, 'Updated text')

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                'SELECT raw_text FROM transcripts WHERE timestamp = ?',
                (entry.timestamp,)
            )
            raw = cursor.fetchone()[0]

        assert raw == 'Original text'  # Must remain unchanged

    def test_update_nonexistent_entry_returns_false(self, history_manager):
        """Updating non-existent entry should return False."""
        success = history_manager.update_entry('2026-01-01T00:00:00.000000', 'Text')
        assert success is False

    def test_update_entry_visible_in_get_recent(self, history_manager):
        """Updated text should be reflected in get_recent."""
        entry = history_manager.add_entry('Original')
        history_manager.update_entry(entry.timestamp, 'Updated')

        entries = history_manager.get_recent(1)
        assert entries[0].text == 'Updated'


class TestDeleteEntry:
    """Test deleting entries."""

    def test_delete_entry_removes_from_database(self, history_manager, temp_db):
        """Entry should be removed from database."""
        entry = history_manager.add_entry('To be deleted')
        success = history_manager.delete_entry(entry.timestamp)

        assert success is True

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                'SELECT COUNT(*) FROM transcripts WHERE timestamp = ?',
                (entry.timestamp,)
            )
            count = cursor.fetchone()[0]

        assert count == 0

    def test_delete_nonexistent_entry_returns_false(self, history_manager):
        """Deleting non-existent entry should return False."""
        success = history_manager.delete_entry('2026-01-01T00:00:00.000000')
        assert success is False

    def test_delete_entry_not_in_get_recent(self, history_manager):
        """Deleted entry should not appear in get_recent."""
        entry = history_manager.add_entry('To delete')
        history_manager.delete_entry(entry.timestamp)

        entries = history_manager.get_recent()
        assert entry.timestamp not in [e.timestamp for e in entries]


class TestClear:
    """Test clearing all history."""

    def test_clear_removes_all_entries(self, history_manager, temp_db):
        """clear() should delete all transcripts."""
        for i in range(5):
            history_manager.add_entry(f'Entry {i}')

        history_manager.clear()

        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM transcripts')
            count = cursor.fetchone()[0]

        assert count == 0

    def test_clear_preserves_schema(self, history_manager, temp_db):
        """Schema should remain intact after clear."""
        history_manager.add_entry('Test')
        history_manager.clear()

        # Should be able to add entries again
        entry = history_manager.add_entry('After clear')
        assert entry.text == 'After clear'


class TestRotation:
    """Test automatic rotation of old entries."""

    def test_rotation_removes_oldest_entries(self, temp_db):
        """When exceeding limit, oldest entries should be removed."""
        # Create fresh manager and set max_entries to 3
        from utils import ConfigManager
        ConfigManager.set_config_value(3, 'output_options', 'max_history_entries')
        
        # Create new history manager with clean database
        hm = HistoryManager(history_file=temp_db)

        # Add 5 entries
        for i in range(5):
            hm.add_entry(f'Entry {i}')

        # Should have only 3 newest entries
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM transcripts')
            count = cursor.fetchone()[0]

        assert count == 3

        # Verify oldest were removed
        remaining = hm.get_recent(10)
        assert len(remaining) == 3
        assert remaining[2].text == 'Entry 2'  # Oldest remaining
        assert remaining[0].text == 'Entry 4'   # Newest


class TestExport:
    """Test export functionality."""

    def test_export_txt_format(self, history_manager, tmp_path):
        """Should export to plain text format."""
        history_manager.add_entry('First entry', 100)
        history_manager.add_entry('Second entry', 200)

        export_path = tmp_path / 'export.txt'
        success = history_manager.export_to_file(export_path, format='txt')

        assert success is True
        assert export_path.exists()
        content = export_path.read_text()
        assert 'First entry' in content
        assert 'Second entry' in content

    def test_export_csv_format(self, history_manager, tmp_path):
        """Should export to CSV format with headers."""
        history_manager.add_entry('CSV test', 500)

        export_path = tmp_path / 'export.csv'
        success = history_manager.export_to_file(export_path, format='csv')

        assert success is True
        content = export_path.read_text()
        assert 'Timestamp,Text,Duration (ms)' in content
        assert 'CSV test' in content
        assert '500' in content

    def test_export_markdown_format(self, history_manager, tmp_path):
        """Should export to Markdown with formatted headers."""
        history_manager.add_entry('Markdown test', 1000)

        export_path = tmp_path / 'export.md'
        success = history_manager.export_to_file(export_path, format='md')

        assert success is True
        content = export_path.read_text()
        assert '# Vociferous Transcription History' in content
        assert 'Markdown test' in content
        assert 'Duration: 1000ms' in content


class TestHistoryEntry:
    """Test HistoryEntry dataclass."""

    def test_to_display_string_short_text(self):
        """Should display full text if under max_length."""
        entry = HistoryEntry('2026-01-07T10:30:45.123456', 'Short text', 100)
        display = entry.to_display_string(max_length=80)

        assert display == '[10:30:45] Short text'

    def test_to_display_string_long_text(self):
        """Should truncate text if over max_length."""
        long_text = 'A' * 100
        entry = HistoryEntry('2026-01-07T10:30:45.123456', long_text, 100)
        display = entry.to_display_string(max_length=50)

        assert display.startswith('[10:30:45] ')
        assert display.endswith('...')
        # max_length applies to text preview only, display includes timestamp
        assert 'AAAA' in display
        assert len(display) < 100  # Substantially shorter than original
