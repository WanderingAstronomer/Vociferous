# Vociferous Changelog

---

# v1.4.2 - Comprehensive Error Isolation

**Date:** January 2026  
**Status:** Release

---

## Summary

Stability-focused release implementing comprehensive error isolation across all signal handlers, callbacks, and critical operations. Introduces new error handling utilities (`safe_callback`, `safe_slot_silent`) and adds deferred model invalidation to prevent segfaults during focus group operations.

## Major Changes

### Error Isolation Framework

**New Utilities:**
- `safe_callback(fn, context)` - Wraps lambda signal handlers to catch & log exceptions silently
- `safe_slot_silent(context)` - Decorator for background operations (log-only, no dialog)

**Philosophy:**
- **User actions** → Error dialog (explicit feedback via `@safe_slot`)
- **Background ops** → Log-only (silent failure via `@safe_slot_silent`)
- **Lambda handlers** → `safe_callback()` wrapper (isolated errors)

### Deferred Model Invalidation

**Problem:** Segfault when assigning transcripts to focus groups from the Recent tab. Root cause: proxy model called `invalidateFilter()` during context menu callback, corrupting the `QModelIndex` mid-operation.

**Solution:** Introduced `QTimer` with 0ms interval to defer filter invalidation until after the callback completes:

```python
self._invalidate_timer = QTimer()
self._invalidate_timer.setSingleShot(True)
self._invalidate_timer.setInterval(0)
self._invalidate_timer.timeout.connect(self.invalidateFilter)

# Signal connections now use deferred invalidation
self._connections = [
    (history_manager.entryUpdated, safe_callback(
        lambda _: self._invalidate_timer.start(), "entryUpdated")),
]
```

### Protected Components

| Component | Protection Added |
|-----------|------------------|
| `FocusGroupTree` | try/except + logging on all CRUD methods |
| `HistoryTreeView` | `safe_callback` on context menu lambdas, error handling on CRUD |
| `FocusGroupProxyModel` | `safe_callback` on signal lambdas, protected `filterAcceptsRow()` |
| `KeyListener` | Error isolation in `_trigger_callbacks()` |
| `ResultThread` | try/except around audio callback |
| `Sidebar` | `safe_callback` on lambda signal connections |

### UI Bug Fixes

- **Fixed**: Ghost context menus appearing on deleted transcript locations
- **Fixed**: Sidebar collapsing when deleting transcripts from Recent/Focus Groups
- **Fixed**: Recording stopping when deleting a transcript during recording
- **Fixed**: Header text overflow (month/day/timestamp truncation)
- **Fixed**: Welcome text font size too large

## Files Modified (10)

- `src/ui/utils/error_handler.py` - Added `safe_callback()`, `safe_slot_silent()`
- `src/ui/utils/__init__.py` - Exported new utilities
- `src/ui/widgets/focus_group/focus_group_tree.py` - Protected all CRUD methods
- `src/ui/widgets/history_tree/history_tree_view.py` - Protected CRUD, wrapped lambdas
- `src/ui/models/focus_group_proxy.py` - Deferred invalidation, protected filters
- `src/ui/components/sidebar/sidebar_new.py` - Wrapped lambda connections
- `src/key_listener.py` - Isolated callback errors
- `src/result_thread.py` - Protected audio callback
- `src/ui/components/main_window/main_window.py` - Error handling on slots
- `src/ui/constants/typography.py` - Reduced `GREETING_SIZE` (48px → 24px)

## Testing

- **29 error handling tests** including new integration tests
- **All tests passing** with no regressions
- Tests cover: `safe_callback`, `safe_slot_silent`, error isolation in KeyListener, model edge cases

## Technical Notes

- Deferred invalidation pattern prevents Qt model/view corruption during callbacks
- All exceptions now logged to `~/.local/share/vociferous/logs/vociferous.log`
- Error isolation ensures one failing callback doesn't break subsequent callbacks
- No segfaults possible from focus group operations

---

# v1.4.1 - Design System Consolidation & Error Handling

**Date:** January 2026  
**Status:** Release

---

## Summary

Architecture refinement release focused on design system consolidation and code hygiene. Introduces Refactoring UI-compliant typography and spacing scales, consolidates all per-widget styles into a single unified stylesheet, adds structured error handling with user-facing dialogs, and removes 12 unused files from the codebase.

## Major Changes

### Design System Consolidation

**Typography Scale (Refactoring UI compliant):**
- Hand-crafted scale: 11, 13, 16, 20, 24, 32, 48px
- Two weights only: 400 (normal), 600 (emphasis)
- No orphan sizes or arbitrary values

**Spacing Scale (non-linear):**
- 8-step scale: 4, 8, 12, 16, 24, 32, 48, 64px
- Semantic aliases: `APP_OUTER=16`, `MAJOR_GAP=16`, `MINOR_GAP=8`
- All magic numbers replaced with named constants

**Color System (3-tier text hierarchy):**
- `TEXT_PRIMARY=#d4d4d4` - Main content
- `TEXT_SECONDARY=#888888` - Supporting text
- `TEXT_TERTIARY=#555555` - Disabled/hints
- Consolidated accent color: `PRIMARY=#5a9fd4`

### Unified Stylesheet Architecture
- **Consolidated**: All per-widget `*_styles.py` files merged into `unified_stylesheet.py`
- **Removed**: Redundant StylesheetRegistry and Theme classes
- **Pattern**: Single `generate_unified_stylesheet()` applied at app startup
- **Benefit**: No per-widget `setStyleSheet()` calls, consistent styling, faster startup

### Error Handling Framework
- **Added**: `error_handler.py` - Centralized error management
- **Added**: `error_dialog.py` - User-facing error notification dialogs
- **Added**: `test_error_handling.py` - Comprehensive error handling tests
- **Pattern**: Structured try/except → log → optionally show dialog

### Documentation Update
- **Added**: `docs/images/recording_state.png` - Recording state screenshot

## Files Removed (12)

### Orphan Modules
- `src/input_simulation.py` - Unused input injection code

### Redundant Style Files (now in unified_stylesheet.py)
- `src/ui/components/settings/settings_styles.py`
- `src/ui/components/sidebar/sidebar_styles.py`
- `src/ui/components/title_bar/title_bar_styles.py`
- `src/ui/components/workspace/workspace_styles.py`
- `src/ui/widgets/focus_group/focus_group_styles.py`
- `src/ui/widgets/history_tree/history_tree_styles.py`

### Orphan Sidebar Components
- `src/ui/components/sidebar/sidebar.py` - Replaced by sidebar_new.py
- `src/ui/components/sidebar/sidebar_edge.py` - Unused

### Dead Infrastructure
- `src/ui/styles/stylesheet_registry.py` - Replaced by unified stylesheet
- `src/ui/styles/theme.py` - Unused theme abstraction
- `src/ui/widgets/history_tree/history_tree_delegate_new.py` - Orphan delegate

## Testing

- **All 142 tests passing** (1 skipped intentionally)
- **mypy clean**: 86 source files, 0 errors
- **No regressions** in existing functionality

## Technical Notes

- Design system follows Refactoring UI best practices for visual hierarchy
- Unified stylesheet eliminates style duplication and ordering issues
- Centralized constants enable systematic design changes
- Error handling improves debugging without disrupting user experience

---

# v1.4.0 - UI Overhaul & Comprehensive Metrics Framework

**Date:** January 10, 2026  
**Status:** Ready for refinement engine phase

---

## Summary

Complete visual redesign and metrics foundation. Implemented focus groups UI with dynamic sidebar, functional search system, real-time waveform visualization, and comprehensive transcription analytics framework. The UI now provides transparency about the cognitive and productivity dimensions of dictation.

## Major Features

### Focus Groups Management
- **Implemented**: Complete focus groups UI with visual sidebar
- **Added**: Dynamic focus group tree with custom delegation and font sizing
- **Added**: Create/rename/delete focus groups through sidebar context menu
- **Added**: Proper visual distinction and color coding for focus groups

### Recent Transcripts View
- **Implemented**: Recent transcripts tab showing last 7 days of activity
- **Added**: Clean, organized transcript listing with timestamps
- **Added**: Quick access to recently dictated content

### Search System
- **Implemented**: Full-text search across all transcripts
- **Added**: Real-time search interface integrated into sidebar
- **Added**: Highlight matching transcripts in search results
- **Added**: Clear/cancel search functionality

### Waveform Visualization
- **Implemented**: Real-time audio waveform display during recording
- **Added**: Visual feedback for recording state
- **Added**: Waveform scaling and responsive design
- **Added**: Integration with recording lifecycle

### Metrics Framework

#### Per-Transcription Metrics (Row 0: Human vs Machine Time)
- **Recording Time**: Total human cognitive time (speaking + thinking)
- **Speech Duration**: Machine-processed speech time (VAD-filtered segments from Whisper)
- **Silence Time**: Absolute time spent thinking/pausing (calculated as difference)

#### Per-Transcription Metrics (Row 1: Productivity & Efficiency)
- **Words/Min**: Idea throughput (words per minute of cognitive time)
- **Typing-Equivalent Time Saved**: Time saved vs manual composition at 40 WPM
- **Speaking Rate**: Pure articulation speed during active speech (WPM excluding pauses)

#### Lifetime Analytics (Bottom Bar)
- **Total Spent Transcribing**: Cumulative recording time across all transcripts
- **Total Saved by Transcribing**: Total time saved vs typing (all transcripts combined)
- **Total Transcriptions**: Count of completed transcriptions
- **Total Transcription Word Count**: Cumulative words across entire history

#### Metrics Explanation Dialog
- **Added**: Help → Metrics Calculations detailed documentation
- **Explains**: Definition and formula for each metric
- **Explains**: Philosophy: "Silence is not waste — it's cognition"
- **Explains**: Explicit assumptions (40 WPM typing baseline)
- **Explains**: How raw duration differs from machine-processed time

### UI/UX Refinements
- **Added**: Dynamic greeting message (Good Morning/Afternoon/Evening based on time of day)
- **Improved**: Typography scale (greeting 42pt, body 19pt, focus group names 17pt)
- **Improved**: Spacing and padding throughout (GREETING_TOP_MARGIN 16px, tab buttons 18px 24px)
- **Added**: Sidebar tab bar with bold text (font-weight 700)
- **Added**: Tab text wrapping (white-space: normal)
- **Added**: Tooltip on "Typing-Equivalent Time Saved" metric (semantic anchoring)
- **Added**: Search button styling (transparent background)
- **Moved**: Metrics display above content box (cleaner layout, no overlay issues)
- **Fixed**: Button height alignment (44px for text buttons, matching search button)

### Database & Backend

#### Speech Duration Tracking
- **Added**: `speech_duration_ms` column to transcripts table (schema v1 → v2)
- **Added**: Automatic schema migration for existing databases
- **Implemented**: VAD segment extraction from Whisper transcribe output
- **Implemented**: Speech duration calculation in transcription pipeline

#### Data Flow
- **Updated**: `result_thread.py` to extract and pass `speech_duration_ms`
- **Updated**: `transcription.py` to return `tuple[str, int]` (text, speech_duration_ms)
- **Updated**: `history_manager.py` to persist dual-duration metrics
- **Updated**: All database queries to handle speech_duration_ms

### Architecture Improvements
- **Removed**: Orphan metrics widgets (fixed Wayland window tiling bug)
- **Separated**: Metrics display from content panel (workspace-level ownership)
- **Centralized**: All typography constants in typography.py
- **Centralized**: All spacing constants in spacing.py

## Changes by Category

### Files Modified: 132
### Commits: Ready for single comprehensive commit

### Component Files Updated
- `src/ui/components/sidebar/` - Focus groups, tab bar, styling
- `src/ui/components/workspace/` - Metrics, content layout, header
- `src/ui/components/main_window/` - Menu integration for metrics dialog
- `src/ui/widgets/` - Custom dialogs, waveform, focus group tree
- `src/ui/constants/` - Typography and spacing scales
- `src/` - Core pipeline updates for metrics data

### Database Files
- `src/history_manager.py` - Schema v2 migration
- `src/transcription.py` - VAD duration extraction
- `src/result_thread.py` - Dual-duration threading

## Testing
- All existing tests passing
- Manual testing of metrics with live recordings
- Verified graceful degradation for pre-migration transcripts
- Verified Wayland compatibility (no floating windows)

## Philosophy & Design Decisions

**Silence is measurement, not waste.** This release introduces a measurement framework that treats thinking time as a first-class concern. Rather than hiding pauses or assuming they don't exist, Vociferous now:

1. Separates human time (recording) from machine time (speech)
2. Makes cognitive time explicit and measurable (silence time)
3. Derives productivity metrics that account for thinking
4. Provides complete transparency via explanation dialog
5. Never misleads about time saved

The metrics are not about guilt or optimization; they're about understanding the dictation experience.

## Next Phase

Refinement engine implementation planned. This provides the technical foundation for:
- Advanced text corrections powered by context
- Grammar and style improvements
- Transcript enhancement workflows

---

# v1.3.0 Beta - Focus Groups (Data Layer)

**Date:** January 2026  
**Status:** Beta

---

## Summary

Backend implementation of Focus Groups (Foci) - user-defined organization for transcripts. Provides complete CRUD operations for grouping transcripts by subject or purpose. UI integration deferred to future release.

## Changes

### Focus Group Data Layer

- **Added**: `create_focus_group(name)` - Create new focus groups with user-defined names
- **Added**: `get_focus_groups()` - Retrieve all focus groups ordered by creation date
- **Added**: `rename_focus_group(id, new_name)` - Rename existing focus groups
- **Added**: `delete_focus_group(id, move_to_ungrouped)` - Delete groups with safety controls:
  - Default behavior: move transcripts to ungrouped (via `ON DELETE SET NULL` foreign key)
  - Optional blocking: prevent deletion if group contains transcripts
- **Added**: `assign_transcript_to_focus_group(timestamp, group_id)` - Move transcripts between groups or to ungrouped (None)
- **Added**: `get_transcripts_by_focus_group(group_id, limit)` - Filter transcripts by group membership

### Database Enforcement

- **Enforced**: Foreign key constraints via `PRAGMA foreign_keys = ON` in all relevant methods
- **Enforced**: `ON DELETE SET NULL` cascade behavior - deleting a group automatically ungroupes its transcripts
- **Added**: Transaction-level foreign key enforcement for data integrity

### Testing

- **Added**: 14 comprehensive unit tests covering:
  - Focus group creation, listing, renaming, deletion
  - Transcript assignment and filtering by group
  - Foreign key cascade behavior (ungrouping on delete)
  - Blocking deletion of non-empty groups
  - Ungrouped transcript queries (NULL group_id)
- **Verified**: All 41 tests passing (27 original + 14 focus group tests)
- **Verified**: Zero regressions in existing functionality

## Behavioral Notes

- **Ungrouped is default**: Transcripts without a focus group assignment have `focus_group_id = NULL`
- **Exactly one place**: Each transcript belongs to zero or one focus group (no multiple assignments)
- **Safe deletion**: Foreign key constraint ensures transcripts never reference deleted groups

## UI Status

- **No user-facing changes**: Focus groups are fully implemented in the data layer but not yet exposed in the UI
- **Future work**: Phase 2 UI integration will add sidebar navigation, group management dialogs, and filtered transcript views

---

# v1.2.0 Beta - SQLite Migration

**Date:** January 2026  
**Status:** Beta

---

## Summary

Major persistence layer overhaul replacing JSONL storage with SQLite database. Introduces foundational schema for future features including focus groups (Phase 2) and content refinement (Phase 4+). All existing functionality preserved with improved performance for updates and queries.

## Changes

### Storage & Data Model

- **Migrated**: Complete replacement of JSONL file storage with SQLite database (`~/.config/vociferous/vociferous.db`)
- **Added**: `transcripts` table with dual-text architecture:
  - `raw_text` - Immutable audit baseline (what Whisper produced)
  - `normalized_text` - Editable content (target for user edits and future refinement)
  - Both fields initialized to identical values on creation
- **Added**: `focus_groups` table (currently unused, ready for Phase 2 navigation)
- **Added**: `schema_version` table for future database migrations
- **Added**: Auto-increment integer primary keys (`id`) for stable references
- **Added**: Foreign key constraint from `transcripts.focus_group_id` to `focus_groups(id)` with `ON DELETE SET NULL`
- **Added**: Database indexes on `id DESC`, `timestamp`, and `focus_group_id` for efficient queries
- **Enforced**: `raw_text` immutability - no code path modifies raw transcription after creation
- **Enforced**: Foreign key constraints via `PRAGMA foreign_keys = ON`

### API & Compatibility

- **Preserved**: Complete API compatibility - all `HistoryManager` methods maintain identical signatures
- **Preserved**: `HistoryEntry` dataclass unchanged (timestamp, text, duration_ms)
- **Preserved**: Export functionality for txt, csv, and markdown formats
- **Preserved**: Automatic rotation when exceeding `max_history_entries` config value
- **Changed**: Internal ordering now uses `id DESC` instead of `created_at DESC` for deterministic sort order
- **Changed**: Rotation deletes by `id ASC` (oldest entries) instead of timestamp-based sorting

### Testing

- **Added**: Comprehensive test suite with 27 new unit tests covering:
  - Database initialization and schema validation
  - CRUD operations (create, read, update, delete)
  - `raw_text` immutability enforcement
  - `normalized_text` editability
  - Export format validation
  - Rotation behavior
  - Fixture isolation for clean test state
- **Added**: Database-backed test fixtures using temporary SQLite files
- **Verified**: All 77 existing tests pass with zero regressions

### Breaking Changes

- **Removed**: Legacy JSONL storage support (no migration path from existing history files)
- **Note**: Users will start with fresh history after upgrade - existing `~/.config/vociferous/history.jsonl` is no longer read

## Technical Notes

- SQLite ordered by auto-increment ID ensures insertion order preserved even with rapid successive entries
- `created_at` timestamp retained for future time-based queries but not used for ordering
- Schema designed to support Phase 2 (focus groups) and Phase 4+ (refinement) without structural changes
- Database location consistent with existing config directory pattern

---

# v1.1.1 Beta - Documentation Refresh

**Date:** December 2025  
**Status:** Beta

---

## Summary

Documentation-focused update: clarified current behavior (press-to-toggle only), aligned wiki with ARCHITECTURE.md as source of truth, and fixed mermaid diagrams.

## Changes

- **Wiki refresh**: Replaced Recording page to reflect single supported mode (press-to-toggle); updated Text Output, Config Options, Keycodes Reference, Hotkey System, Backend Architecture, Threading Model, and Home navigation links.
- **Architecture link-out**: Added guidance to treat ARCHITECTURE.md as canonical; wiki pages now act as concise summaries.
- **Mermaid fixes**: Corrected High-Level Architecture diagram label (main.py/VociferousApp) and refreshed data-flow/threading diagrams in wiki to render properly.
- **Config clarification**: Documented `recording_mode` as fixed to `press_to_toggle`; noted default Alt hotkey captures both Alt keys (known limitation).

## Notes

- No functional code changes; this release is purely documentation and clarity improvements.

---

# v1.1.0 Beta - Custom Title Bar & History Enhancements

**Date:** December 2025  
**Status:** Beta

---

## Summary

Feature release introducing a custom frameless title bar with unified menu/controls, enhanced history management with file watching and persistent deletion, a Cancel button for aborting recordings, and bundled application icons.

---

## Changes

### Custom Title Bar

- **Added**: Custom frameless `TitleBar` widget with menu bar, centered title, and window controls (minimize, maximize, close) in a single row
- **Added**: Wayland-native drag support via `startSystemMove()` for proper window dragging on Wayland compositors
- **Added**: X11 fallback drag handling for traditional window movement
- **Added**: Double-click title bar to maximize/restore window
- **Added**: Styled window controls with hover effects (blue highlight for min/max, red for close)
- **Added**: Border styling for frameless window (`1px solid #3c3c3c`, `border-radius: 6px`)
- **Added**: `QT_WAYLAND_DISABLE_WINDOWDECORATION=1` environment variable for client-side decorations on Wayland

### History Widget Enhancements

- **Added**: `QFileSystemWatcher` with 200ms debounce to auto-reload history when file changes externally
- **Added**: `delete_entry()` method in HistoryManager for persistent deletion from JSONL file
- **Added**: Delete key shortcut with `Qt.ApplicationShortcut` context for reliable deletion even when focus shifts
- **Added**: `historyCountChanged` signal to track entry count for UI state updates
- **Added**: `entry_count()` helper method for counting non-header entries
- **Added**: Automatic fallback selection after deletion (prefers previous entry, then next)
- **Added**: Automatic day header removal when all entries under a day are deleted
- **Fixed**: History widget now accepts `HistoryManager` in constructor for proper initialization order

### Main Window Improvements

- **Added**: Cancel button in current transcription panel to abort recording without transcribing
- **Added**: `cancelRecordingRequested` signal connected to `_cancel_recording()` in main app
- **Added**: History menu "Open History File" action to open JSONL file in system default handler
- **Added**: `_update_history_actions()` method to enable/disable Export controls based on history count
- **Fixed**: Export button, menu action, and Ctrl+E shortcut now disabled when history is empty
- **Fixed**: Guard added to `_export_history()` to show status message when nothing to export
- **Changed**: `display_transcription()` now accepts `HistoryEntry` for consistent timestamps
- **Changed**: `load_entry_for_edit()` no longer steals focus (cursor position preserved)
- **Changed**: Placeholder text updated to "Your transcription will appear here..."

### Application Icons

- **Added**: Bundled icon assets in `icons/` directory:
  - `512x512.png` - High-resolution application icon
  - `192x192.png` - Medium-resolution icon
  - `favicon.ico` - Windows/multi-resolution icon
- **Changed**: Tray icon now loads from bundled assets with fallback to theme icon

### Launcher Script

- **Added**: `RUST_LOG=error` environment variable to suppress verbose wgpu/Vulkan warnings

### Bug Fixes

- **Fixed**: Unused `datetime` import removed from main_window.py (ruff compliance)
- **Fixed**: Result thread now properly sets `self.result_thread = None` on completion to prevent stale references
- **Fixed**: History widget initialization order ensures buttons exist before loading history (prevents AttributeError)

---

# v1.0.1 Beta - UI Polish & Editing Support

**Date:** December 2025  
**Status:** Beta

---

## Summary

Refinement release focusing on UI polish and introducing editable transcriptions. History entries can now be edited directly in the main window, and the layout has been simplified to a fixed 50/50 split.

---

## Changes

### History Widget Behavior

- **Single-click** on history entry loads it into editor for modification
- **Double-click** copies entry to clipboard
- **Removed**: Re-inject functionality (replaced by copy/paste workflow)
- **Removed**: Tooltips on history items (cleaner appearance)
- **Fixed**: Timestamp format now consistently shows "10:03 a.m." style

### Main Window Layout

- **Replaced**: QSplitter with fixed 50/50 horizontal layout (no resize handle)
- **Added**: Editable transcription panel with Save button
- **Added**: `update_entry()` in HistoryManager for saving edits

### Settings Dialog

- **Added**: Device setting (auto/cuda/cpu) exposed in UI
- **Added**: Dynamic compute_type filtering based on device selection
- **Fixed**: float16 automatically falls back to float32 on CPU

### Project Structure

- **Moved**: Scripts reorganized into `scripts/` folder
  - `run.py` → `scripts/run.py`
  - `install.sh` → `scripts/install.sh`
  - `check_deps.py` → `scripts/check_deps.py`
- **Updated**: `vociferous.sh` references `scripts/run.py`

### Documentation

- **Updated**: README.md to match current codebase
- **Updated**: ARCHITECTURE.md with accurate module descriptions
- **Fixed**: Install and run paths reference `scripts/` folder

---

# v1.0.0 Beta - Polished UI & History System

**Date:** December 2025  
**Status:** Beta

---

## Summary

Major milestone release introducing a full-featured main window with transcription history, graphical settings dialog, and a simplified clipboard-only workflow. The floating status window has been replaced with an integrated UI that provides history management, export capabilities, and live configuration updates.

---

## Breaking Changes from Alpha

### UI Architecture

- **Removed**: `StatusWindow` and `BaseWindow` classes (floating frameless windows)
- **Removed**: Automatic text injection (unreliable on Wayland)
- **Replaced with**: `MainWindow` with integrated history and transcription panels
- **Replaced with**: Clipboard-only output (always copies, user pastes with Ctrl+V)

### Configuration

- **Removed**: `output_options.input_method` auto-inject options (pynput/ydotool/dotool direct typing)
- **Removed**: `output_options.auto_copy_clipboard`, `auto_inject_text`, `auto_submit_return` cascading options
- **Simplified**: All transcriptions now copy to clipboard automatically

---

## What's New

### Main Window

A full application window replaces the minimal floating status indicator:

```
┌──────────────────────────────────────────────────────┐
│ File  History  Settings  Help                        │
├──────────────────────────────────────────────────────┤
│ ┌──History────────┐ │ ┌──Current Transcription────┐ │
│ │ ▼ December 14th │ │ │                           │ │
│ │   10:03 a.m. ...│ │ │  Transcribed text here    │ │
│ │   9:45 a.m. ... │ │ │                           │ │
│ │ ▼ December 13th │ │ │       ● Recording         │ │
│ │   ...           │ │ │                           │ │
│ └─────────────────┘ │ └───────────────────────────┘ │
│ [Export] [Clear All]│ [Copy]            [Clear]     │
└──────────────────────────────────────────────────────┘
```

**Features:**
- **Dark theme** with blue accents (#1e1e1e background, #5a9fd4 highlights)
- **Responsive layout**: Side-by-side at ≥700px, stacked below
- **Resizable splitter** with visual grab handle
- **Window geometry persistence** (remembers size/position)
- **System tray integration** with minimize-to-tray behavior
- **One-time tray notification** when first minimized

### History System

Persistent transcription history with JSONL storage:

- **Storage**: `~/.config/vociferous/history.jsonl` (append-only, thread-safe)
- **Day grouping**: Entries organized under collapsible day headers (▼/▶)
- **Friendly timestamps**: "December 14th" headers, "10:03 a.m." entry times
- **Visual nesting**: Indented entries under day headers with styled headers
- **Auto-rotation**: Configurable max entries (default 1000)

**History Widget:**
- Click day headers to collapse/expand
- Double-click entries to copy
- Right-click context menu: Copy, Re-inject, Delete
- Keyboard navigation (Enter to copy, Delete to remove)

**Export:**
- **Text** (`.txt`): Timestamped entries
- **CSV** (`.csv`): Spreadsheet-compatible with headers
- **Markdown** (`.md`): `## Date` and `### Time` heading hierarchy

### Settings Dialog

Schema-driven graphical preferences dialog:

- Accessible via **Settings → Preferences** or **tray right-click → Settings**
- Dynamically built from `config_schema.yaml`
- Each schema section becomes a tab (Model Options, Recording Options, Output Options)
- Widget types inferred from schema (`bool` → checkbox, `str` with options → dropdown)
- Tooltips display setting descriptions
- Changes apply immediately (Apply or OK)

### Hotkey Rebinding

Live hotkey capture in Settings:

1. Click **Change...** next to Activation Key
2. Press desired key combination
3. Validation blocks reserved shortcuts (Alt+F4, Ctrl+C, etc.)
4. New hotkey active immediately—no restart required

**Implementation:**
- `HotkeyWidget` with capture mode
- `KeyListener.enable_capture_mode()` diverts events to callback
- `keycode_mapping.py` utilities for display/config string conversion

### Live Configuration Updates

Settings changes take effect without restart:

| Setting | Effect |
|---------|--------|
| `activation_key` | KeyListener reloads immediately |
| `input_backend` | Backend switches (evdev ↔ pynput) |
| `compute_type`, `device` | Whisper model reloads |

**Signal architecture:**
- `ConfigManager.configChanged(section, key, value)` signal
- Main app connects handlers for each setting type

### Recording Indicator

Compact pulsing indicator in the current transcription panel:

- **Recording**: Red "● Recording" with opacity pulse animation (0.3 ↔ 1.0)
- **Transcribing**: Orange "● Transcribing" (solid)
- **Idle**: Hidden

### UI Polish

- **Floating pill headers** with rounded borders for panel labels
- **Custom Clear History dialog** with Yes/No button layout (Yes left, No right)
- **Styled scrollbars** matching dark theme
- **Menu bar**: File, History, Settings, Help (View menu removed)
- **Keyboard shortcuts**: Ctrl+C (copy), Ctrl+E (export), Ctrl+H (focus history), Ctrl+L (clear)

---

## Files Added

```
src/
├── history_manager.py      # JSONL storage with rotation and export
└── ui/
    ├── history_widget.py   # Collapsible day-grouped history display
    ├── hotkey_widget.py    # Live hotkey capture widget
    ├── keycode_mapping.py  # KeyCode ↔ string utilities
    ├── main_window.py      # Primary application window (820 lines)
    ├── output_options_widget.py  # (Cascading checkboxes - deprecated)
    └── settings_dialog.py  # Schema-driven preferences dialog

tests/
└── test_settings.py        # Settings, hotkey, and config signal tests
```

## Files Removed

```
src/ui/
├── base_window.py          # Frameless window base class
└── status_window.py        # Floating status indicator

assets/
├── microphone.png          # Recording icon (now using text indicator)
├── pencil.png              # Transcribing icon
└── ww-logo.png             # Application logo (now using system theme icon)
```

## Files Modified

- **main.py**: Replaced StatusWindow with MainWindow, added HistoryManager, removed InputSimulator direct typing, clipboard-only workflow
- **input_simulation.py**: Added `reinitialize()` for live updates, auto-detection of input method
- **key_listener.py**: Added capture mode for hotkey rebinding
- **utils.py**: ConfigManager now extends QObject, emits `configChanged` and `configReloaded` signals
- **config_schema.yaml**: Simplified schema, marked internal options with `_internal: true`
- **run.py**: Suppresses Qt Wayland warnings

---

## Known Issues

- **Button padding**: Minor spacing issue between Export/Clear buttons and history pane bottom edge
- **Recording indicator font**: Slight font size inconsistency on the active recording indicator

---

## Platform Notes

### Wayland

The clipboard-only workflow was adopted because automatic text injection via ydotool/dotool is unreliable when window focus shifts during transcription. Copying to clipboard and letting the user paste with Ctrl+V is more robust.

### Model Caching

Model loading now tries `local_files_only=True` first to avoid unnecessary HTTP requests to HuggingFace, only downloading if not cached.

---

---

# v0.9.0 Alpha - Complete Architectural Rewrite

**Date:** December 2025  
**Status:** Pre-release

---

## Summary

Complete ground-up rewrite of Vociferous. The previous architecture (v0.7-v0.8) featured a daemon-based server, Kivy GUI, CLI with multiple commands, and support for multiple transcription engines. This release replaces it entirely with a minimal, focused design: a single-purpose hotkey-triggered dictation tool.

---

## Breaking Changes

**This version is not compatible with any previous version.** The entire codebase has been replaced.

### Architecture Removed

- **Daemon Server** - FastAPI-based background process with REST API
- **Kivy GUI** - Multi-screen application (home, settings, history)
- **CLI Commands** - `transcribe`, `daemon`, `bench`, `check`, `deps`
- **Multiple Engines** - Canary-Qwen, model registry, hardware detection
- **Configuration Presets** - Complex schema with validation and profiles
- **Progress System** - Rich progress tracking with callbacks

### Architecture Replaced With

- **Direct Execution** - Single `run.py` entry point, no daemon
- **Minimal UI** - PyQt5 status window + system tray icon
- **Hotkey Activation** - Press key to record, press again to transcribe
- **Single Engine** - faster-whisper only (distil-large-v3 default)
- **Simple Config** - YAML schema with sensible defaults

---

## New Design Philosophy

| Aspect | v0.8.x (Previous) | v0.9.0 (Current) |
|--------|-------------------|------------------|
| Source files | 60+ files in `vociferous/` | 8 files in `src/` |
| Test files | 50+ test files, 376 tests | 5 test files |
| UI framework | Kivy (Material Design) | PyQt5 (minimal) |
| Transcription | Daemon with REST API | Direct in-process |
| Engines | Multiple (registry-based) | faster-whisper only |
| Configuration | Pydantic schemas, presets | Simple YAML |
| Input detection | pynput only | evdev (Wayland) + pynput fallback |
| Text injection | pynput only | dotool/ydotool/pynput/clipboard |

---

## Rationale

The v0.7-v0.8 architecture was designed for a full-featured transcription application with batch processing, multiple engines, and GUI-driven workflows. The rewrite focuses on a single use case: **real-time dictation**.

**Why rewrite?**
1. **Simplicity** - Daemon architecture added complexity without benefit for dictation
2. **Wayland support** - Previous pynput-only approach broken on modern Linux
3. **Startup speed** - No daemon means instant activation
4. **Maintainability** - 8 files vs 60+ files

---

## What's New

### Wayland-First Input Handling

- **evdev backend** - Works on Wayland (requires `input` group membership)
- **pynput fallback** - Automatic fallback for X11 users
- **Multi-backend text injection** - dotool, ydotool, pynput, clipboard

### GPU Bootstrap Pattern

- Process re-executes with correct `LD_LIBRARY_PATH` for CUDA libraries
- Sentinel variable prevents infinite re-exec loop
- Works transparently - users just run `python run.py`

### Minimal UI

- Frameless floating status window
- Shows recording/transcribing state
- System tray for background operation
- No configuration dialogs (edit YAML directly)

### Simplified Installation

- `install.sh` creates venv, installs deps, verifies imports
- `check_deps.py` validates all required packages
- Single `requirements.txt` with pinned versions

---

## Files (New Structure)

```
Vociferous/
├── run.py                  # Entry point with GPU bootstrap
├── install.sh              # Installation script
├── check_deps.py           # Dependency validator
├── requirements.txt        # Pinned dependencies
├── src/
│   ├── main.py             # VociferousApp orchestrator
│   ├── utils.py            # ConfigManager singleton
│   ├── key_listener.py     # Hotkey detection (evdev/pynput)
│   ├── result_thread.py    # Audio recording & transcription
│   ├── transcription.py    # faster-whisper integration
│   ├── input_simulation.py # Text injection backends
│   ├── config_schema.yaml  # Configuration schema
│   └── ui/
│       ├── base_window.py  # Frameless window base
│       └── status_window.py # Status indicator
├── tests/                  # Minimal test suite
└── docs/
    └── ARCHITECTURE.md     # Comprehensive architecture guide
```

---

## Files Removed (136 files)

All files from the previous architecture deleted:
- `vociferous/` package (app, audio, cli, config, domain, engines, gui, server, setup)
- `tests/` subdirectories (app, audio, cli, config, domain, engines, gui, integration, refinement, server)
- Documentation (Design.md, daemon.md, Redesign.md, GUI recommendations)

---

## Migration

**There is no migration path.** v0.9.0 is a new application sharing only the name. If you relied on the daemon API, CLI commands, or Kivy GUI, those features no longer exist.

---

## Credits

The v0.1-v0.8 architecture served as exploration of what a full-featured transcription tool could look like. This rewrite takes the lessons learned and applies them to a simpler, more focused tool.`  