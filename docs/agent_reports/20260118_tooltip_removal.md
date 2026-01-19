# Agent Research Journal - Tooltip Removal Task

## System Understanding and Assumptions
- The user has requested the removal of all hover-over tooltip text pop-ups across the entire UI.
- Previous architectural decisions seem to have already moved towards tooltip prohibition (as evidenced by `tests/test_ui_contracts.py`).
- A preliminary scan of the codebase shows that `setToolTip` is NOT actively used in any `src/` files (only one commented-out occurrence remains).
- The user also requested to "amend or remove any related tests". This refers to the `TestTooltipProhibitions` class and other assertion-based tests that verify the absence of tooltips.

## Identified Invariants and Causal Chains
- Invariant: UI elements must not show text on hover.
- Causal Chain: User hovers -> Tooltip event triggered -> Tooltip shown (This needs to be broken or ensured to be null).

## Data Flow and Ownership Reasoning
- Tooltips are owned by individual `QWidget` instances.
- Global tooltip behavior can be influenced by `QApplication` or QSS, but the standard way is per-widget.

## UI Intent -> Execution Mappings
- The intent is "No Tooltips".
- Execution:
    1. Verify no `setToolTip` calls exist. (Done, none found active).
    2. Explicitly set tooltips to empty strings in components that might have them by default (e.g., `QSystemTrayIcon`, `QToolButton`).
    3. Remove or transition the "prohibition" tests since they are now the "standard" rather than a special case to be tested for specific widgets, OR keep them if they serve as a safeguard. Given the user said "amend or remove", I will remove them if they are redundant or redundant to a more global check.

## Trade-offs and Decisions
- Decision: I will keep the prohibition tests for now but move them to a more central place if they are scattered, or just remove them if they are specifically mentioned as "related tests" to be removed.
- Decision: I will add a global event filter or a check in a base class if possible, but the codebase doesn't seem to have a common base class for ALL widgets that I can easily edit without affecting stability. 
- Better Decision: I will specifically check `SystemTrayManager` and `RailButton` as they are the most likely candidates for "default" tooltips that the user might be seeing.

## Task Plan
1. Confirm no active `setToolTip` in `src/ui/`. (Confimred via grep).
2. Check `QSystemTrayIcon` in `src/ui/components/main_window/system_tray.py` and ensure `setToolTip` is not called implicitly or by default.
3. Check `RailButton` in `src/ui/components/main_window/icon_rail.py`.
4. Remove the `TestTooltipProhibitions` class in `tests/test_ui_contracts.py` as requested.
5. Run tests to ensure no regressions.
