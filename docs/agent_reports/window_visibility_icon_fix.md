# Window Visibility and Icon Fix

**Date**: 2026-01-18  
**Status**: Complete  
**Scope**: System Tray, Window Management, Application Icon

---

## Problem Statement

User reported two related issues:

1. **System Tray Toggle Failure**: Clicking the system tray icon would hide the window, but clicking again would not restore it. Only restarting the application could restore the window.

2. **Missing Application Icon**: When minimized to the taskbar/dock, the application window showed a generic gear cog icon instead of the Vociferous microphone icon.

---

## Root Cause Analysis

### Issue 1: System Tray Toggle Failure

**Location**: `src/ui/components/main_window/system_tray.py`

**Cause**: The `toggle_main_window()` method relied on `QMainWindow.isVisible()` to determine window visibility state:

```python
def toggle_main_window(self) -> None:
    if not self.main_window.isVisible():
        self.main_window.show()
        # ...
    else:
        self.main_window.hide()
```

**Problem**: On Wayland and some window managers, `isVisible()` returns unreliable results after `hide()` is called, causing the toggle logic to always think the window is visible and continuously calling `hide()`.

### Issue 2: Missing Application Icon

**Location**: `src/core/application_coordinator.py`

**Cause**: The application was only setting the window icon on the `MainWindow` instance:

```python
self.main_window.setWindowIcon(SystemTrayManager.build_icon(self.app))
```

**Problem**: The application-wide window icon (used by taskbar/dock) was never set. This requires calling `QApplication.setWindowIcon()`, not just `QMainWindow.setWindowIcon()`.

---

## Solution Implementation

### Fix 1: Explicit State Tracking for Window Visibility

**File**: `src/ui/components/main_window/system_tray.py`

**Changes**:

1. Added explicit state tracking flag in `__init__`:
   ```python
   # Explicit visibility state tracking to handle unreliable isVisible()
   # on some window managers (particularly Wayland compositors)
   self._window_is_hidden = False
   ```

2. Updated `toggle_main_window()` to use explicit state:
   ```python
   def toggle_main_window(self) -> None:
       if self._window_is_hidden:
           self.main_window.show()
           self.main_window.activateWindow()
           self.main_window.raise_()
           self._window_is_hidden = False
       else:
           self.main_window.hide()
           self._window_is_hidden = True
   ```

**Rationale**: By tracking visibility state explicitly in a boolean flag that we control, we eliminate dependency on the window manager's potentially unreliable visibility reporting. This ensures deterministic toggle behavior across all platforms.

### Fix 2: Application-Wide Icon Setup

**File**: `src/core/application_coordinator.py`

**Changes**:

1. Extracted icon creation to a variable for reuse:
   ```python
   # Set application-wide window icon (for taskbar/dock representation)
   # and main window icon (for system tray compatibility)
   app_icon = SystemTrayManager.build_icon(self.app)
   self.app.setWindowIcon(app_icon)
   self.main_window.setWindowIcon(app_icon)
   ```

**Rationale**: 
- `QApplication.setWindowIcon()` sets the default icon for all windows in the application, used by the taskbar/dock
- `QMainWindow.setWindowIcon()` sets the icon for that specific window, used by window managers and system trays
- Setting both ensures comprehensive icon coverage

---

## Test Updates

**File**: `tests/test_application_coordinator.py`

**Changes**:

1. Added `QIcon` import:
   ```python
   from PyQt6.QtGui import QIcon
   ```

2. Updated `coordinator_patches` fixture to return a valid `QIcon` from `build_icon()`:
   ```python
   # Make SystemTrayManager.build_icon() return a valid QIcon
   mock_tray.build_icon.return_value = QIcon()
   ```

3. Updated `test_engine_no_respawn_during_shutdown` with same mock setup

**Rationale**: The tests mock `SystemTrayManager` which caused `build_icon()` to return a `MagicMock`. The real `QApplication.setWindowIcon()` requires a genuine `QIcon` instance, so we configure the mock to return an empty (but valid) `QIcon()`.

---

## Validation

### Test Results
- All 496 tests pass (3 xfailed)
- No new test failures introduced
- Both modified coordinator tests pass

### Linting
- `ruff check .` → All checks passed
- `mypy` on modified files → Success: no issues found

### Behavioral Verification Required

The user should verify:

1. **System Tray Toggle**:
   - Click system tray icon → window hides
   - Click system tray icon again → window restores and becomes active
   - Repeat 3-5 times to confirm consistency

2. **Application Icon**:
   - Minimize window using title bar minimize button
   - Check taskbar/dock for Vociferous microphone icon (not gear cog)
   - Click dock icon → window should restore

---

## Architecture Compliance

### Intent Pattern
✅ No violations. System tray toggle is a direct user action handled by `SystemTrayManager`, not propagated through intent layer (correct for system-level affordances).

### Data Layer
✅ N/A. No database or persistence changes.

### Threading
✅ No threading changes. Window operations remain on main Qt thread.

### Configuration
✅ No config changes. Uses existing `ResourceManager.get_icon_path("system_tray_icon")`.

---

## Lessons Learned

1. **Platform Assumptions**: Never assume Qt's `isVisible()` is reliable across all window managers. Wayland compositors in particular have different visibility semantics than X11.

2. **Icon Hierarchy**: Application icons require setting at two levels:
   - `QApplication.setWindowIcon()` for global taskbar/dock representation
   - `QMainWindow.setWindowIcon()` for per-window icon (system tray, window decorations)

3. **Test Mocking Precision**: When mocking Qt components, mock return values must match expected types exactly. `MagicMock` is not an acceptable substitute for `QIcon` in production code paths.

---

## References

- **Qt6 Documentation**: `qapplication.html#setWindowIcon`
- **Wayland Protocol**: Window state visibility semantics differ from X11
- **Vociferous Architectural Guidelines**: Section 4.2 (Background Execution and Threading)
