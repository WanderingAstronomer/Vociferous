"""
Comprehensive UI component tests for dialogs, widgets, and interactions.

Tests Focus Groups, History Tree, Settings Dialog, and other UI components.
"""

import pytest
from PyQt6.QtWidgets import QApplication

from history_manager import HistoryManager
from key_listener import KeyListener
from ui.components.settings import SettingsDialog
from ui.models import TranscriptionModel
from ui.widgets.dialogs import CreateGroupDialog
from ui.widgets.focus_group import FocusGroupContainer, FocusGroupTreeWidget
from ui.widgets.history_tree import HistoryTreeView
from ui.widgets.hotkey_widget import HotkeyWidget


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def temp_history_manager(tmp_path):
    """Create a temporary history manager for testing."""
    db_path = tmp_path / "test_history.db"
    return HistoryManager(db_path)


@pytest.fixture
def key_listener():
    """Create a key listener for testing."""
    return KeyListener()


# ============================================================================
# Create Group Dialog Tests
# ============================================================================


class TestCreateGroupDialog:
    """Tests for the Create Focus Group dialog."""

    def test_dialog_creation(self, qapp):
        """Test that dialog can be created."""
        dialog = CreateGroupDialog()
        assert dialog is not None
        assert dialog.windowTitle() == ""  # Custom title bar

    def test_default_color_selected(self, qapp):
        """Test that Ocean Blue color is selected by default."""
        dialog = CreateGroupDialog()
        # Default color is the first in the list (Ocean Blue)
        assert dialog._selected_color == "#3a5f7f"

    def test_color_selection(self, qapp):
        """Test changing color selection."""
        dialog = CreateGroupDialog()

        # Select third color (Goldenrod)
        new_color = "#b8860b"
        dialog._on_color_selected(new_color)

        assert dialog._selected_color == new_color

        # Verify only one swatch is selected
        selected_count = sum(1 for s in dialog._color_swatches if s._selected)
        assert selected_count == 1

    def test_name_input_enables_create_button(self, qapp):
        """Test that entering a name enables the Create button."""
        dialog = CreateGroupDialog()

        # Initially disabled
        assert not dialog.create_btn.isEnabled()

        # Enter name
        dialog.name_input.setText("My Group")
        dialog._on_name_changed("My Group")

        # Now enabled
        assert dialog.create_btn.isEnabled()

    def test_empty_name_disables_create_button(self, qapp):
        """Test that empty name keeps Create button disabled."""
        dialog = CreateGroupDialog()

        dialog.name_input.setText("Something")
        dialog._on_name_changed("Something")
        assert dialog.create_btn.isEnabled()

        # Clear the name
        dialog.name_input.setText("")
        dialog._on_name_changed("")

        assert not dialog.create_btn.isEnabled()

    def test_get_result(self, qapp):
        """Test getting the dialog result."""
        dialog = CreateGroupDialog()

        dialog.name_input.setText("Test Group")
        dialog._on_name_changed("Test Group")
        dialog._on_color_selected("#5a3e4f")

        name, color = dialog.get_result()
        assert name == "Test Group"
        assert color == "#5a3e4f"


# ============================================================================
# Focus Group Widget Tests
# ============================================================================


class TestFocusGroupWidget:
    """Tests for Focus Group tree widget and container."""

    def test_tree_creation(self, qapp, temp_history_manager):
        """Test creating the focus group tree widget."""
        tree = FocusGroupTreeWidget(temp_history_manager)
        assert tree is not None
        assert tree.topLevelItemCount() == 0

    def test_load_empty_groups(self, qapp, temp_history_manager):
        """Test loading when no groups exist."""
        tree = FocusGroupTreeWidget(temp_history_manager)
        tree.load_groups()
        assert tree.topLevelItemCount() == 0

    def test_create_group(self, qapp, temp_history_manager):
        """Test creating a focus group."""
        tree = FocusGroupTreeWidget(temp_history_manager)

        group_id = tree.create_group("Test Group", "#3a4f5c")

        assert group_id is not None
        assert tree.topLevelItemCount() == 1

        # Verify group data (text is in column 1, column 0 is for color bar)
        item = tree.topLevelItem(0)
        assert "Test Group" in item.text(1)
        assert item.data(0, tree.ROLE_GROUP_ID) == group_id
        assert item.data(0, tree.ROLE_COLOR) == "#3a4f5c"

    def test_multiple_groups(self, qapp, temp_history_manager):
        """Test creating multiple focus groups."""
        tree = FocusGroupTreeWidget(temp_history_manager)

        tree.create_group("Group 1", "#3a4f5c")
        tree.create_group("Group 2", "#5a7a6d")
        tree.create_group("Group 3", "#6b5237")

        assert tree.topLevelItemCount() == 3

    def test_group_with_transcripts(self, qapp, temp_history_manager):
        """Test that group shows name (count display removed per user preference)."""
        tree = FocusGroupTreeWidget(temp_history_manager)

        # Create group and add transcript
        group_id = tree.create_group("My Group", "#3a4f5c")
        entry = temp_history_manager.add_entry("Test transcription")
        temp_history_manager.assign_transcript_to_focus_group(entry.timestamp, group_id)

        # Reload to see changes
        tree.load_groups()

        item = tree.topLevelItem(0)
        # Text is in column 1 - count display was removed per user preference
        assert "My Group" in item.text(1)

    def test_container_signals(self, qapp, temp_history_manager):
        """Test that container emits correct signals."""
        container = FocusGroupContainer(temp_history_manager)

        created_signals = []
        container.groupCreated.connect(
            lambda gid, name: created_signals.append((gid, name))
        )

        # Create a group via the tree
        group_id = container.tree.create_group("Signal Test", "#3a4f5c")

        # Signal should have been emitted
        assert len(created_signals) == 1
        assert created_signals[0][0] == group_id
        assert created_signals[0][1] == "Signal Test"


# ============================================================================
# History Tree View Tests
# ============================================================================


class TestHistoryTreeView:
    """Tests for the history tree view with model."""

    def test_tree_creation(self, qapp, temp_history_manager):
        """Test creating history tree view."""
        model = TranscriptionModel(temp_history_manager)
        tree = HistoryTreeView(model)

        assert tree is not None
        assert tree.entry_count() == 0

    def test_add_entry_updates_view(self, qapp, temp_history_manager):
        """Test that adding entry updates the tree."""
        model = TranscriptionModel(temp_history_manager)
        tree = HistoryTreeView(model)

        # Add entry to model
        entry = temp_history_manager.add_entry("Test transcription")
        model.add_entry(entry)

        qapp.processEvents()

        # Tree should show 1 entry
        assert tree.entry_count() == 1

    def test_multiple_entries_grouped_by_day(self, qapp, temp_history_manager):
        """Test that multiple entries from same day are grouped."""
        model = TranscriptionModel(temp_history_manager)
        tree = HistoryTreeView(model)

        # Add multiple entries
        for i in range(3):
            entry = temp_history_manager.add_entry(f"Entry {i}")
            model.add_entry(entry)

        qapp.processEvents()

        assert tree.entry_count() == 3
        # Should have 1 day header with 3 entries
        assert model.rowCount() == 1  # 1 day header
        day_index = model.index(0, 0)
        assert model.rowCount(day_index) == 3  # 3 entries under day

    def test_delete_entry(self, qapp, temp_history_manager):
        """Test deleting an entry from the tree."""
        model = TranscriptionModel(temp_history_manager)
        tree = HistoryTreeView(model)
        tree.set_history_manager(temp_history_manager)

        # Add entry
        entry = temp_history_manager.add_entry("To be deleted")
        model.add_entry(entry)

        qapp.processEvents()
        assert tree.entry_count() == 1

        # Delete it
        model.delete_entry(entry.timestamp)

        qapp.processEvents()
        assert tree.entry_count() == 0

    def test_entry_selection_emits_signal(self, qapp, temp_history_manager):
        """Test that selecting an entry emits signal."""
        model = TranscriptionModel(temp_history_manager)
        tree = HistoryTreeView(model)

        # Add entry
        entry = temp_history_manager.add_entry("Selectable entry")
        model.add_entry(entry)
        qapp.processEvents()

        # Track selection signal
        selected = []
        tree.entrySelected.connect(lambda text, ts: selected.append((text, ts)))

        # Get the entry index (row 0 under day 0)
        day_index = model.index(0, 0)
        entry_index = model.index(0, 0, day_index)

        # Simulate click
        tree._on_item_clicked(entry_index)

        assert len(selected) == 1
        assert selected[0][0] == "Selectable entry"


# ============================================================================
# Hotkey Widget Tests
# ============================================================================


class TestHotkeyWidgetValidation:
    """Tests for hotkey widget validation logic."""

    def test_widget_creation(self, qapp, key_listener):
        """Test creating hotkey widget."""
        widget = HotkeyWidget(key_listener)
        assert widget is not None
        assert widget.display.isReadOnly()

    def test_set_hotkey_displays_correctly(self, qapp, key_listener):
        """Test setting hotkey updates display."""
        widget = HotkeyWidget(key_listener)

        widget.set_hotkey("ctrl+shift+a")

        # Display should show formatted version
        text = widget.display.text()
        assert len(text) > 0  # Should have some text

    def test_validate_empty_hotkey(self, qapp, key_listener):
        """Test validation rejects empty hotkey."""
        widget = HotkeyWidget(key_listener)

        valid, error = widget._validate_hotkey("")

        assert not valid
        assert "No keys" in error

    def test_validate_dangerous_combo(self, qapp, key_listener):
        """Test validation rejects dangerous system shortcuts."""
        widget = HotkeyWidget(key_listener)

        # Test various dangerous combos
        dangerous = ["alt+f4", "ctrl+alt+delete", "ctrl+c", "ctrl+v"]

        for combo in dangerous:
            valid, error = widget._validate_hotkey(combo)
            assert not valid, f"{combo} should be rejected"
            assert "Reserved" in error

    def test_validate_normal_combo(self, qapp, key_listener):
        """Test validation accepts normal shortcuts."""
        widget = HotkeyWidget(key_listener)

        valid, error = widget._validate_hotkey("ctrl+shift+space")

        assert valid
        assert error == ""

    def test_cleanup_disables_capture(self, qapp, key_listener):
        """Test cleanup properly disables capture mode."""
        widget = HotkeyWidget(key_listener)

        # Start capture
        widget._start_capture()

        # Cleanup
        widget.cleanup()

        # Button should be re-enabled
        assert widget.change_button.isEnabled()


# ============================================================================
# Settings Dialog Tests
# ============================================================================


class TestSettingsDialog:
    """Tests for the settings dialog."""

    def test_dialog_creation(self, qapp, key_listener):
        """Test creating settings dialog."""
        dialog = SettingsDialog(key_listener)
        assert dialog is not None

    def test_widgets_populated(self, qapp, key_listener):
        """Test that dialog creates widgets for settings."""
        dialog = SettingsDialog(key_listener)

        # Should have widgets for visible settings
        assert len(dialog.widgets) > 0

    def test_cleanup_on_close(self, qapp, key_listener):
        """Test that dialog cleans up hotkey widget on close."""
        dialog = SettingsDialog(key_listener)

        # Close the dialog
        dialog._cleanup_widgets()

        # Should not crash (hotkey widget cleanup should work)
        assert True  # If we got here, cleanup worked


# ============================================================================
# Model Tests
# ============================================================================


class TestTranscriptionModel:
    """Tests for the transcription model."""

    def test_model_creation(self, qapp, temp_history_manager):
        """Test creating transcription model."""
        model = TranscriptionModel(temp_history_manager)

        assert model is not None
        assert model.rowCount() == 0

    def test_add_entry_increases_count(self, qapp, temp_history_manager):
        """Test adding entry increases row count."""
        model = TranscriptionModel(temp_history_manager)

        entry = temp_history_manager.add_entry("First entry")
        model.add_entry(entry)

        # Should have 1 day header
        assert model.rowCount() == 1

    def test_entry_data_roles(self, qapp, temp_history_manager):
        """Test that model provides correct data for different roles."""
        model = TranscriptionModel(temp_history_manager)

        entry = temp_history_manager.add_entry("Test data roles")
        model.add_entry(entry)

        # Get entry index
        day_index = model.index(0, 0)
        entry_index = model.index(0, 0, day_index)

        # Check various roles
        assert entry_index.data(model.FullTextRole) == "Test data roles"
        assert entry_index.data(model.TimestampRole) == entry.timestamp
        assert entry_index.data(model.IsHeaderRole) is False

        # Day header should have IsHeaderRole = True
        assert day_index.data(model.IsHeaderRole) is True

    def test_update_entry_text(self, qapp, temp_history_manager):
        """Test updating entry text."""
        model = TranscriptionModel(temp_history_manager)

        entry = temp_history_manager.add_entry("Original text")
        model.add_entry(entry)

        # Update the text
        model.update_entry(entry.timestamp, "Modified text")

        # Verify change
        day_index = model.index(0, 0)
        entry_index = model.index(0, 0, day_index)
        assert entry_index.data(model.FullTextRole) == "Modified text"

    def test_signals_emitted(self, qapp, temp_history_manager):
        """Test that model emits signals on changes."""
        model = TranscriptionModel(temp_history_manager)

        added_signals = []
        deleted_signals = []

        model.entryAdded.connect(lambda ts: added_signals.append(ts))
        model.entryDeleted.connect(lambda ts: deleted_signals.append(ts))

        # Add entry
        entry = temp_history_manager.add_entry("Signal test")
        model.add_entry(entry)

        assert len(added_signals) == 1

        # Delete entry
        model.delete_entry(entry.timestamp)

        assert len(deleted_signals) == 1
