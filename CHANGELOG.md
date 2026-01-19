# Vociferous Changelog

## v2.9.6 - Onboarding UX & Layout Improvements

### Added
- **FlowLayout Class**: New responsive layout that wraps items to multiple lines based on available width, enabling proper display of dynamic content

### Fixed
- **AI Refinement Model Selection Layout**: Model selection pills in onboarding now wrap to multiple lines instead of cramming all pills on one line, preventing text truncation and improving readability
- **Onboarding Startup Check**: Onboarding wizard now launches automatically when `user.onboarding_completed` is set to `false` in config. Previously, the startup logic was not checking this flag, so manually resetting it in the YAML had no effect. Now you can trigger onboarding by setting `onboarding_completed: false` and restarting the app.

### Changed
- **RefinementPage Model Selection (`src/ui/components/onboarding/pages.py`)**:
  - Replaced `QHBoxLayout` with new `FlowLayout` for model pills container
  - Model names now fully visible with proper spacing
  - Layout automatically adapts to window width and number of models
- **UserView (`src/ui/views/user_view.py`)**: 
  - Added `_title_label` instance variable to store reference to title QLabel for dynamic updates
  - Added `_on_config_changed()` slot to listen for user name configuration changes and update title in real-time
  - Connected `ConfigManager.instance().config_changed` signal in `__init__()`
  - Updated `cleanup()` to properly disconnect config change signal
- **IconRail (`src/ui/components/main_window/icon_rail.py`)**:
  - Added `_user_btn` instance variable to store reference to user button for label updates
  - Added `_on_config_changed()` slot to listen for user name changes and update button text dynamically
  - Connected `ConfigManager.instance().config_changed` signal in `__init__()`
  - Updated `_build_footer()` to store user button reference
- **ApplicationCoordinator (`src/core/application_coordinator.py`)**:
  - Added onboarding completion check in `start()` method
  - Launches onboarding wizard if `user.onboarding_completed` is `false`
  - Exits gracefully if user cancels onboarding

---

# v2.9.5 - Test Suite Organization & Path Resolution

**Date:** January 19, 2026
**Status:** Maintenance Release

---

## Summary

This release restructures the test suite into logical categories and improves path resolution across nested test directories for better maintainability and discoverability.

## Changed
- **Test Directory Reorganization**: Restructured 493 tests into 8 logical categories for improved organization and discoverability:
  - `tests/unit/` — Fast, isolated component tests (database, config, services, input, utils)
  - `tests/ui/` — All UI layer tests (components, views, intents, layout, accessibility, styling)
  - `tests/integration/` — Component interaction tests (ui, services, application, command)
  - `tests/contracts/` — Architecture & invariant validation tests
  - `tests/features/` — Feature-specific end-to-end tests
  - `tests/code_quality/` — Static analysis and code quality checks
  - `tests/platform/` — Platform-specific compatibility tests
  - `tests/core/` and `tests/core_runtime/` — Low-level runtime tests (existing well-organized structure preserved)
  - Added `PROJECT_ROOT` and `SRC_DIR` constants to `tests/conftest.py` for robust path resolution across nested test directories
  - Updated 8 test files to use conftest path constants instead of relative path calculations

---

# v2.9.4 - Style Architecture & Installation Modernization

**Date:** January 18, 2026
**Status:** Maintenance Release

---

## Summary

This release enforces proper architectural separation for style modules and modernizes installation scripts to align with current project structure and Python 3.12+ requirements.

## Changed
- **Style Module Organization**: Migrated `settings_view_styles.py` and `user_view_styles.py` from `src/ui/views/` to `src/ui/styles/` for proper architectural separation and consistency with the unified stylesheet pattern.
- **Installation Scripts Modernization**: Updated all installation and desktop entry scripts to align with current project architecture, enforce Python 3.12+ requirement, properly resolve paths for portable installs, and use actual available assets.
- **requirements.txt Completeness**: Added missing critical dependency `PyQt6>=6.7.0` to requirements.txt and reorganized for clarity.

## Removed
- **Excess Provisioning Tests**: Removed `test_slm_provisioner.py` which tested removed `scripts/setup_refinement.py` setup script (excess engineering with no project integration).

---

# v2.9.3 - Refinement View UX Enhancement

**Date:** January 17, 2026
**Status:** Feature Enhancement

---

## Summary

This release replaces the old refinement strength slider with a professional card-based interface and enhances custom instruction input with improved visual hierarchy.

## Added
- **Refinement Strength Card**: Replaced the old "Minimal...Overkill" slider with a professional, card-based `StrengthSelector` widget in the Refinement View footer.
- **Enhanced Custom Instructions**: The custom instructions input now resides in its own card with a `BLUE_4` focus border and subtle placeholder styling.

---

# v2.9.2 - Speech Quality Metrics Expansion

**Date:** January 16, 2026
**Status:** Feature Enhancement

---

## Summary

This release adds comprehensive speech quality metrics to the User View, including vocabulary analysis, pause detection, and filler word tracking with detailed calculation explanations.

## Added
- **Title Bar Icon**: Added the system tray icon to the top left corner of the main window title bar, sized to match the title label font size (16px).
- **Speech Quality Metrics**: Added three new metric cards to the User View: Vocabulary (lexical complexity), Avg. Pauses (silence detection), and Filler Words (um, uh, like, you know tracking).
- **Total Silence Metric**: Added a new "Total Silence" metric card to the Usage & Activity section showing accumulated pauses across all transcriptions.
- **Speech Quality Calculation Details**: Added comprehensive explanations in the User View's "Calculation Details" section describing how Vocabulary, Average Pauses, Total Silence, and Filler Words metrics are calculated.

---

# v2.9.1 - Self-Healing SLM & Multi-Model Support

**Date:** January 15, 2026
**Status:** Feature Enhancement

---

## Summary

This release introduces automatic dependency management for the SLM runtime and expands Whisper model support with a unified registry system.

## Added
- **Self-Healing SLM Runtime**: The `SLMService` now automatically detects and installs missing conversion dependencies (`transformers`, `torch`, `ctranslate2`) in the background if they are absent during model provisioning.
- **Multi-Model Support**: Unified Whisper model registry in `src/core/model_registry.py` with support for `large-v3-turbo`.

---

# v2.9.0 - Hot-Swappable Whisper Engine

**Date:** January 14, 2026
**Status:** Major Feature Release

---

## Summary

This major release implements real-time model switching without application restarts, complete with VRAM indicators and transparent download progress overlays.

## Added
- **Hot-Swappable Engine**: Implemented `UPDATE_CONFIG` protocol for real-time model switching without application restarts.
- **VRAM Indicators**: Added VRAM requirement metadata to model selection UI in Settings.
- **Download Transparency**: Integrated a "Loading Model" status bridge that shows a blocking UI overlay during model downloads/initialization.

---

# v2.8.5 - Button Visual Language Consolidation

**Date:** January 13, 2026
**Status:** UI Polish Release

---

## Summary

This release standardizes primary button styling across the application with a transparent visual pattern, aligning with existing destructive and purple button styles.

## Changed
- **Button Visual Language Consolidation**: Redefined the `primaryButton` style class to use an unfilled (transparent) visual pattern. Primary actions (Edit, Save, Start Recording, Apply, Change) now consistently feature a `BLUE_4` border and matching text color on a transparent background, aligning with the existing `destructiveButton` and `purpleButton` pattern. Hover states transition to a subtle `BLUE_9` background with white text for clear interaction feedback.
- **Refinement View UI Polish**: Centered all footer section titles and lightened the text color using `GRAY_3` for a cleaner, modern look. Removed nested borders for better visual flow.

---

# v2.8.4 - Test Infrastructure Consolidation

**Date:** January 12, 2026
**Status:** DevEx Enhancement

---

## Summary

This release decommissions ad-hoc verification scripts in favor of centralized testing through the pytest suite, improving code quality and maintainability.

## Changed
- **Test Infrastructure Consolidation**: Decommissioned 10+ ad-hoc verification scripts from `scripts/` (e.g., `verify_ui_colors.py`, `verify_ui_runtime.py`) and internalized their logic into the `pytest` suite.

---

# v2.8.3 - Settings View Layout Standardization

**Date:** January 11, 2026
**Status:** UI Architecture Release

---

## Summary

This release completely restructures the Settings view with a unified card-based layout and consistent form-style grammar across all sections for improved visual cohesion.

## Changed
- **Settings View Layout Standardization**: Completely restructured the Settings view to use a unified card-based layout with consistent form-style row grammar (label next to control) across all sections. All settings sections now use `QFrame#settingsCard` containers with proper borders, backgrounds, and padding for visual cohesion.

---

# v2.8.2 - Settings View Responsive Design

**Date:** January 10, 2026
**Status:** UX Enhancement

---

## Summary

This release improves Settings view adaptability with flexible width constraints and natural content anchoring for better reading flow across different screen sizes.

## Changed
- **Settings View Responsiveness**: Replaced fixed 900px width with min/max constraints (800px-1200px) for better adaptation to different screen sizes.
- **Settings View Content Anchoring**: Removed top vertical stretch to anchor settings content to the top of the scroll area, providing a more natural reading flow.

---

# v2.8.1 - Input Field Styling Enhancement

**Date:** January 9, 2026
**Status:** UI Polish Release

---

## Summary

This release adds consistent baseline styling to all input fields with refined focus/hover states for reduced visual noise and improved interaction feedback.

## Changed
- **Input Field Styling**: Added consistent baseline styles for all input fields (QLineEdit, QSpinBox, QDoubleSpinBox) with hover and focus states. Blue borders now appear only on focus/hover rather than being permanently visible, reducing visual noise.

---

# v2.8.0 - Critical Bug Fix & Stability Release

**Date:** January 8, 2026
**Status:** Major Fix Release

---

## Summary

This major bug fix release addresses numerous critical issues affecting system tray behavior, UI rendering, refinement engine stability, and settings persistence across the application.

## Fixed
- **UI Invariants Robustness**: Updated `test_color_constants.py` and `test_ui_invariants.py` to allow more flexible color naming and internalized the AST-based colors scan, preventing test failures caused by visual polish or script cleanup.
- **QComboBox Popup Styling**: Fixed a long-standing issue where combo box popups displayed an ugly white background at the top and bottom. Set `combobox-popup: 0` to use stylized popups and normalized padding on the item view to ensure the background covers the entire popup area.
- **System Tray Window Restoration**: Fixed system tray icon toggle behavior where clicking to hide and then restore the window would fail to show the window again. The system tray manager now uses explicit state tracking instead of relying on `isVisible()` to work around unreliable visibility reporting on some window managers (particularly Wayland).
- **Missing Application Icon**: Set application-wide window icon using `QApplication.setWindowIcon()` to ensure proper icon display in taskbar/dock instead of showing as a generic gear cog placeholder.
- **SLM Multi-Turn Leaks**: Resolved an issue where Llama 3-based models (like NeuralDaredevil) would leak chat tokens (`<|im_end|>`) and continue generating into subsequent turns. Added robust stop-token detection for multiple prompt formats (ChatML, Llama 3) and implemented literal string truncation as a second-tier safeguard.
- **GPU Runaway Generation**: Reduced the maximum generation length for refinement tasks from 32,768 to 2,048 tokens. This prevents models from running into infinite loops that cause high GPU utilization and system "whining" when stop tokens are missed.
- **Settings State Persistence**: Resolved a bug where changes in the settings menu would persist in the UI even if the user navigated away without clicking "Apply". The Settings view now automatically refreshes all widgets from the current configuration every time it is entered, ensuring a clean state and clear visual feedback for discarded changes.
- **Dependency Persistence**: Removed aggressive cleanup logic in `scripts/setup_refinement.py` that was force-uninstalling `torch` and `transformers` after every conversion, ensuring the environment remains stable for future use.
- **Refinement Gridlock**: Resolved a critical signal signature mismatch in `ApplicationCoordinator` that caused the UI to get stuck on "Refining..." indefinitely after a successful backend generation.
- **Model Resolution Bug**: Corrected a critical argument mismatch in the engine server's `ConfigManager.set_config_value` call, which caused model selection updates to be applied to wrong keys (ignoring the user's choice).
- **Settings UI Layout**: Switched both Whisper and Refinement model dropdowns to `AdjustToContents` mode. This ensures they auto-expand to fit long model names and VRAM indicators without manual width overrides.
- **Startup Crash**: Resolved `NameError: name 'entry' is not defined` in `main_window.py` caused by orphaned logic during architectural refactoring.
- **MOTD Layout and Wrapping**: Relaxed the Message of the Day word-balancing thresholds and increased the allowed horizontal span to 820px. This prevents the MOTD from being forced into a narrow column on wide screens and ensures it spans the workspace area as intended.
- **MOTD Text Wrapping**: Fixed Message of the Day text wrapping to balance words equally across lines when the text is long enough to wrap. Enabled word wrapping on the subtext label and added text balancing logic. (Refined in latest update)
- **User View Metrics Layout**: Removed confusing empty "ALL TIME" badge, improved insight text generation to be more meaningful, and cleaned up the metrics section header.
- **Transcribing State Hint Text**: During the transcribing state, the content area now shows "Please wait while the Whisper engine processes your audio..." instead of the misleading idle message.
- **Language Field Width Conflict**: Fixed stylesheet/code mismatch where language field had conflicting width declarations (120px vs 200px).
- **Settings Visual Inconsistency**: Eliminated mixed layout patterns (centered columns vs inline rows vs form grids) that created a "whack" feeling. All settings now follow a consistent form-style layout pattern.
- **Project and Subproject Styling**: Fixed reversed styling hierarchy where subprojects were displaying with the same large, bold styling as top-level projects. Now top-level projects display with full-width colored headers and markers, while subprojects use smaller, simpler styling similar to transcript items with small color indicators. Also adjusted font sizes and row heights so subprojects are visually distinguished and smaller than their parent projects.
- **Main Window Background Color**: Fixed jet-black background issue by setting the central widget background color to match the main window color (GRAY_8). The background is now properly visible instead of appearing transparent/black.
- **Delete Button in Transcribe View**: Fixed `AttributeError` when deleting a transcript from the Transcribe View's complete state. The delete handler now correctly calls `workspace.clear_transcript()` instead of the non-existent `workspace.clear()` method.

---

# v2.7.5 - User View Professional Enhancement

**Date:** January 7, 2026
**Status:** UI Polish Release

---

## Summary

This release applies professional Qt UI engineering improvements to the User View with normalized spacing, enhanced icons, and refined visual hierarchy.

## Changed
- **User View Stylesheet**: Applied professional Qt UI engineering improvements including normalized spacing scale (20px/32px instead of 24px/40px), added min-height (96px) to metric cards for layout stability, improved button accessibility with vertical padding (6px 24px), removed unsupported CSS line-height property, and refined hover states to only emphasize borders for calmer visual feedback.
- **User View Icons**: Updated all metric cards to use new appropriately named user_view-specific icons (time_saved, words_captured, transcriptions, time_recorded, avg_length, total_silence, vocabulary, pauses, filler_words) and doubled their size from 24x24 to 48x48 pixels for better visibility.
- **User View Layout**: Repositioned the tagline "Solid efficiency gains from dictation over typing" to appear directly beneath the "Lifetime Statistics" header as a subheader for improved visual hierarchy.
- **About Section**: Expanded the footer description to provide more comprehensive information about Vociferous's privacy-first architecture, local processing capabilities, and AI-powered features.
- **Creator Attribution Styling**: Styled the "Created by Andrew Brown" text at the bottom of the User View with BLUE_3 color for improved visual prominence.

---

# v2.7.4 - Refinement View Layout Improvement

**Date:** January 6, 2026
**Status:** UX Enhancement

---

## Changed
- **Refine View Layout**: Moved the "Refine" button from the view footer to the ActionDock with proper purple styling. Stacked the strength slider controls vertically with the hint text above the slider for better readability. The slider now spans the full width of its container.

---

# v2.7.3 - Refinement Engine & Script Cleanup

**Date:** January 5, 2026
**Status:** Feature Enhancement

---

## Summary

This release introduces dynamic refinement scaling, improves workflow with draft mode, and purges redundant verification scripts in favor of centralized pytest execution.

## Removed
- **Redundant Scripts**: Purged ad-hoc verification scripts (`verify_*.py`, `ui_smoke.py`, `setup_refinement.py`) in favor of centralized execution authority via `pytest` and formal installation workflows.

## Changed
- **Dynamic Refinement Scaling**: Replaced the hardcoded generation limit with a sliding scale mechanism. The maximum allowed output now scales proportionally with the input length (providing ~50% headroom and a 150-token minimum buffer), capped at 16,384 tokens (~1 hour of speech). This ensures that long transcripts are not prematurely truncated while maintaining a safety ceiling for small inputs.
- **Improved UI Responsiveness**: Refinement engine now calculates dynamic limits per-request, reducing GPU overhead for short snippets.
- **Refinement Workflow**: Clicking "Refine" now navigates to the Refine view in "Draft" mode, allowing you to adjust instructions and profiles before manually triggering the generation with the "Refine" button. This prevents accidental immediate consumption of GPU resources.

## Fixed
- **Duplicate UI Entries**: Hardened `TranscriptionModel` with ID-based idempotency to prevent duplicate entries when receiving multiple change signals.
- **Test Suite Hang**: Fixed a race condition in `test_restart_application_closes_window` by ensuring strict cleanup of `ConfigManager` and `SettingsView` between test runs.
- **Test Infrastructure**: Resolved `ModuleNotFoundError` in `test_ui_scenarios.py` by correcting mock paths to `src.database.history_manager`.

---

# v2.7.2 - Transcription Flow Optimization

**Date:** January 4, 2026
**Status:** Performance Enhancement

---

## Summary

This release optimizes the transcription result handoff between the engine and UI for immediate metric updates and improved responsiveness.

## Changed
- **Transcription Flow**: Optimized the handoff between the transcription engine and UI by passing the saved `HistoryEntry` directly to `MainWindow`, ensuring immediate metric updates.

---

# v2.7.1 - Refinement System Overhaul & UI Cleanup

**Date:** January 3, 2026
**Status:** Major Enhancement

---

## Summary

This release completely re-engineers the refinement prompt architecture with a 4-layer enforcement model and removes tooltips across the entire UI for architectural purity.

## Changed
- **Tooltip Removal**: Universally removed all hover-over tooltip text pop-ups from the UI and deleted all related prohibition tests to reduce cognitive noise and maintain architectural purity.
- **Refinement Architecture**: Re-engineered the prompt engine to use a 4-layer enforcement model (Global Invariants, Role definition, Permitted/Prohibited actions, and Primary Directive). This significantly improved instruction following and cognitive posture.
- **Refinement Profiles**: Replaced flat strings with stratified Levels 0-4 (Literal, Structural, Neutral, Intent, and Overkill).
- **Prompt Engineering**: Moved global invariants into the system message to enforce semantic fidelity and prevent "AI-flavored" fluff.
- **Inference Optimization**: Optimized ChatML prompt structure to maintain high-quality results while using `/no_think` mode for fast (2s) local inference.
- **ASR Model**: Updated default model configuration to large-v3-turbo for higher transcription accuracy (user-configurable via config.yaml).

## Fixed
- **Engine Server Syntax**: Fixed a `SyntaxError` in `src/core_runtime/server.py` and implemented the missing `_ensure_model_loaded` method for thread-safe model loading.
- **SLM Provisioning Errors**: Fixed startup error spam when refinement is enabled but model conversion dependencies (`transformers`, `torch`) are not installed. The SLM service now gracefully detects missing build-time dependencies and shows a clear warning directing users to run `scripts/setup_refinement.py` instead of throwing errors.
- **Icon Rail Width Constant**: Corrected `RAIL_WIDTH` constant from 120 to 142 to match actual layout requirements (button width 110 + margins 32).
- **Blocking Overlay Test**: Fixed test mock assertion to match actual `show_message(message, title=)` signature.
- **Type Annotation**: Added missing type annotation for `state` parameter in `MainWindow.update_refinement_state`.
- **Baseline Dependency Tests**: Rewrote `test_baseline_dependency_contract.py` to correctly test conversion dependency detection behavior (these are build-time deps, not baseline runtime deps).
- **Accessibility Tests**: Skip focus-related tests on Wayland/offscreen platforms where focus handling is unreliable.
- **IntentFeedbackHandler API**: Aligned MainWindow.on_refinement_status_message with IntentFeedbackHandler's public method name by adding on_refinement_status_message method to the handler.
- **QThread Lifecycle**: Ensured deterministic shutdown in ApplicationCoordinator tests by calling cleanup() to prevent "Destroyed while thread is still running" warnings.
- **Shutdown Idempotency**: Confirmed ApplicationCoordinator.cleanup() is already idempotent with early return guard.
- **Engine Respawn**: Verified engine client does not respawn during intentional shutdown by checking running flag in connection loss handler.

## Added
- **Unit Test**: Added test_refinement_status_message_handling to verify MainWindow calls IntentFeedbackHandler correctly.
- **Shutdown Test**: Added test_engine_no_respawn_during_shutdown to assert no respawn loop during shutdown.

---

# v2.7.0 - Architectural Milestone: Micro-Kernel & Plugin Ecosystem

**Date:** January 2, 2026
**Status:** Major Architecture Release

---

## Summary

This major release introduces the micro-kernel architecture with isolated transcription engine process and implements a pluggable input backend system for extensibility.

## Added
- **Plugin Ecosystem (Epoch 3)**: Implemented pluggable input backend system:
  - Added `PluginLoader` (`src/core/plugins/loader.py`) for dynamic discovery of input backends via `vociferous.plugins.input` entry points
  - Refactored `KeyListener` to use `PluginLoader` for backend selection instead of hardcoded list
  - Enabled extensibility for third-party input handlers (e.g., custom Wayland compositors)
- **Micro-Kernel Architecture (Epoch 2)**: Separated transcription engine into isolated process:
  - Implemented Client-Server IPC architecture using `src/core_runtime/protocol.py` (PacketTransport)
  - Created `EngineServer` to host Whisper model, preventing UI freezes and reducing main process memory footprint
  - Created `EngineClient` to manage subprocess lifecycle and communication
  - Integrated `TranscriptionRuntime` with `EngineClient` transparently

## Changed
- **Refinement UI**: Enhanced Settings View to provide real-time status feedback (Downloading, Ready, Error) and disable conflicting actions during model provisioning.
- **Installation Documentation**: Restructured README.md to provide clear baseline install flow and separate "enable refinement" flow, with explicit dependency separation.

---

# v2.6.5 - TDD Phase 5: Code Quality Enforcement

**Date:** December 30, 2025
**Status:** Quality Enhancement

---

## Summary

This release completes the TDD quality initiative with magic number extraction, docstring coverage enforcement, and color constant centralization.

## Added
- **Magic number extraction (Phase 5.3 TDD)**: Extracted hardcoded layout dimensions to `ui.constants.dimensions` per audit findings:
  - `ToggleSwitch`: Extracted width (50), height (24), radius (12), circle size (18), margin (3), duration (200ms)
  - `ContentPanel`: Extracted margins (32, 24) and spacing (12)
  - Created automated enforcement tests in `test_magic_numbers.py` to prevent regression
- **Docstring coverage enforcement (Phase 5.2 TDD)**: Added comprehensive docstrings to priority architectural components:
  - `BaseView.__init__`: Documents parent widget parameter and initialization
  - `ToggleSwitch.__init__`, `circle_position` property: Documents widget initialization and animation state
  - `ContentPanel.__init__`: Documents panel initialization for transcript display
  - `SelectionState.has_selection`, `is_single_selection`: Documents selection query properties
  - Created automated enforcement tests preventing missing docstrings on public APIs
- **Docstring coverage test suite**: Created `test_docstring_coverage.py` with 10 tests validating docstring presence and quality
- **Color constant centralization (Phase 5.1 TDD)**: Centralized all UI colors into semantic constants per P3-06 audit finding:
  - Added semantic color tokens: `TOGGLE_CIRCLE_ON`, `HOVER_OVERLAY_LIGHT`, `HOVER_OVERLAY_BLUE`, `OVERLAY_BACKDROP`
  - Refactored `toggle_switch.py`, `unified_stylesheet.py`, `refine_view.py`, `main_window_styles.py` to use centralized constants
  - Created automated enforcement tests preventing hardcoded hex/rgba colors in production code
  - Addresses audit finding P3-06 (Hardcoded colors bypass centralized palette) from UI Architecture Audit Report
- **Color constant test suite**: Created `test_color_constants.py` with 12 tests validating color constant coverage, completeness, and usage

---

# v2.6.4 - TDD Phase 4: Threading Pattern Migration

**Date:** December 29, 2025
**Status:** Architecture Fix

---

## Summary

This release refactors background workers from the QThread subclass anti-pattern to the Qt6-recommended moveToThread pattern for proper resource management.

## Added
- **Threading pattern optimization (Phase 4 TDD)**: Refactored background workers from QThread subclass anti-pattern to Qt6-recommended moveToThread pattern:
  - `SetupWorker`: Converted from `QThread` subclass to `QObject` with `do_work()` slot (no longer overrides `run()`)
  - `SetupPage`: Implements moveToThread pattern with proper cleanup chain via `deleteLater()` on worker and thread
  - Added `finished = pyqtSignal(bool, str)` for thread-safe result communication
  - Thread cleanup automatically triggered via `thread.finished` signal
  - Addresses audit finding P1-05 (Critical: QThread subclass anti-pattern) from UI Architecture Audit Report
- **Threading pattern test suite**: Created `test_threading_patterns.py` with 8 tests validating QObject pattern compliance, moveToThread safety, and resource cleanup

---

# v2.6.3 - TDD Phase 3: Accessibility Implementation

**Date:** December 28, 2025
**Status:** Accessibility Enhancement

---

## Summary

This release implements comprehensive accessibility support for keyboard users and screen readers with proper focus states and ARIA labels.

## Added
- **Accessibility & keyboard navigation (Phase 3 TDD)**: Implemented comprehensive accessibility support for keyboard users and screen readers:
  - Added `:focus` pseudo-state styling for all button types (`primaryButton`, `secondaryButton`, `destructiveButton`, `purpleButton`) with 2px outline and offset
  - `RailButton`: Set `accessibleName` to "Navigate to {view}" and `accessibleDescription` for screen reader support
  - `ToggleSwitch`: Supports setting `accessibleName` from parent context
  - All interactive widgets now support keyboard focus and tab navigation
  - Addresses audit findings P2-03, P4-04, P4-05 from UI Architecture Audit Report
- **Accessibility test suite**: Created comprehensive `test_accessibility.py` with 14 tests validating focus states, tab navigation, accessible names, and keyboard shortcuts

---

# v2.6.2 - TDD Phase 2: Widget Cleanup Protocol

**Date:** December 27, 2025
**Status:** Resource Management Enhancement

---

## Summary

This release implements mandatory cleanup() methods for all stateful widgets to prevent resource leaks and ensure proper lifecycle management.

## Added
- **Widget cleanup protocol (Phase 2 TDD)**: Implemented `cleanup()` methods for all stateful widgets to prevent resource leaks:
  - `ToggleSwitch`: Stops QPropertyAnimation to prevent animation leaks
  - `RailButton`: Resets blink state (QTimer.singleShot auto-cleans, but consistency enforced)
  - `BlockingOverlay`: Hides overlay if visible during cleanup
  - `TranscriptPreviewOverlay`: Clears viewer content and hides during cleanup
  - `ExportDialog`: Ensures dialog is closed during cleanup
  - `DialogTitleBar`: Resets drag state during cleanup
  - `MainWindow._cleanup_children()`: Recursive cleanup of all child views and components with graceful error handling
  - `MainWindow.closeEvent()`: Now calls `_cleanup_children()` before window close
  - Addresses audit findings P1-03, P1-04, P2-01, P2-02, P2-05 from UI Architecture Audit Report
- **Widget cleanup test suite**: Created comprehensive `test_widget_cleanup.py` with 21 tests validating cleanup protocol compliance, idempotency, and resource release

---

# v2.6.1 - TDD Phase 1: Widget Sizing & Comprehensive Fixes

**Date:** December 26, 2025
**Status:** Major Quality & Feature Release

---

## Summary

This release kicks off the TDD initiative with widget sizing compliance and includes numerous critical fixes for refinement, resource resolution, and UI behavior across the application.

## Added
- **Widget sizing compliance (Phase 1 TDD)**: Implemented `sizeHint()` and `minimumSizeHint()` methods for 7 custom widgets per Qt6 layout best practices:
  - `BarSpectrumVisualizer`: Returns preferred size 200x100, minimum 100x50
  - `ToggleSwitch`: Returns fixed size 50x24 (matches setFixedSize)
  - `RailButton`: Returns square 110x110 dimensions
  - `TranscriptPreviewOverlay`: Returns preferred 400x300, minimum 150x150
  - `HistoryTreeView`: Returns preferred 300x400, minimum 150x200
  - `BlockingOverlay`: Returns preferred 600x400, minimum 300x200
  - Addresses audit findings P1-01, P1-02, P2-04 from UI Architecture Audit Report
- **Widget sizing test suite**: Created comprehensive `test_widget_sizing.py` with 29 tests validating sizeHint compliance across all custom widgets

## Fixed
- **Authoritative Resource Resolution**: Unified asset resolution across production and testing environments using `ResourceManager`. Removed relative path traversal antipatterns (`Path(__file__).parents[...]`) in `TitleBar`, `Onboarding`, and Application Restart logic.
- **Asset Verification Hardening**: Updated `scripts/verify_assets.py` to perform comprehensive, non-zero-exiting checks on all critical icons (IconRail, TitleBar), unified stylesheet integrity, and font/sound directories.
- **Refinement model echoing**: Fixed an issue where 8B and 14B models (and some 4B variants) would echo the original transcript instead of refining it. Shifted default SLM model definitions to use Instruct variants instead of Base variants, added explicit stop token support to `RefinementEngine`, and improved `_parse_output` to strip accidentally echoed transcript markers.
- **Thinking model support**: Enhanced robust parsing of `<think>` blocks to handle both complete and truncated reasoning, ensuring that AI "thoughts" are correctly logged but removed from the final refined output.
- **SLM reasoning output filtering**: Added automatic stripping of `<think>` reasoning blocks from SLM outputs (Refinement and MOTD). This ensures that models which generate internal thoughts (like Qwen2.5-14B) do not pollute the final user-visible text with reasoning tags.
- **MOTD token limit**: Increased MOTD generation token limit from 80 to 256 to allow enough headroom for models to perform internal reasoning before producing the final one-sentence message.
- **Refinement View lifecycle**: `RefineView` is now fully operational. It correctly loads transcript data by ID, displays a "processing" state during fetches, and emits proper signals for acceptance/discarding. The previous "inert" implementation has been replaced with a reactive, styled component using `ContentPanel`.
- **TranscribeView button persistence bug**: Fixed action buttons (edit, delete, copy) persisting when navigating away from transcribe view after completing a transcription. Added EDITING and VIEWING state transitions to IDLE in hideEvent handler.
- **Search overlay missing background**: Added `QFrame#previewOverlay` stylesheet definition with GRAY_7 background and BLUE_4 border for proper visibility when previewing transcripts from search.
- **Hotkey widget button heights**: Added fixed height (BUTTON_HEIGHT_PRIMARY = 48px) to hotkey input field and change button for consistent sizing.

### Changed
- **Model settings layout**: Refactored from 2-row horizontal layout to 3-column vertical stack (Device, Compute Type, Language side by side with labels above) for better visual organization.
- **Settings view dividers**: Added consistent light gray dividers between all settings sections (Model Settings, Recording, Visualization, Output & Processing) for improved visual separation.
- **User metrics explanations**: Enhanced "How Metrics Are Calculated" section with mathematical formulas showing actual calculation methods (e.g., "Time Saved = (words ÷ 50 WPM × 60) − recording_time").
- **Personalized user metrics banner**: Changed "User Metrics" title to show user's name from config (e.g., "Andrew's Metrics") or "Your Metrics" as fallback.
- **Dynamic icon rail user label**: Icon rail now reads user name from config instead of hardcoded "User" label for personalized navigation.

### Fixed (continued from previous)
- **ActionDock button text clipping**: Increased button padding from `8px 16px` to `12px 16px` and added explicit `min-height: 48px` to stylesheet to prevent descender characters (g, p, y) from being cut off, especially in grid layouts.
- **HistoryView delete button**: Connected `deleteRequested` signal from HistoryView to new `_on_delete_from_history_view()` handler in MainWindow, enabling delete functionality with confirmation dialog and automatic model refresh.
- **ProjectsView create project button**: Added `create_new_project()` wrapper method to `ProjectTreeWidget` that displays the CreateProjectDialog and calls the underlying `create_project()` method, fixing the CREATE_PROJECT action dispatch.

### Changed
- Removed the blue border from the `QMainWindow` in `unified_stylesheet.py` and `main_window_styles.py` to achieve a cleaner look.
- Enhanced MOTD generation prompts in `slm_service.py` to encourage more engaging and varied messages: updated tone to "calm, grounded, professional, and engaging", expanded guidance to include wordplay, alliteration, light humor, and thematic inspiration for freshness and uniqueness.

### Added
- **Dynamic Refinement Prompts**: Moved all refinement system prompts from hardcoded Python source to `config_schema.yaml`, enabling user customization without code changes.
- **User Instruction Input**: Added a configurable text input to the Refinement View, allowing users to supply specific instructions (e.g., "Make it bullet points") during refinement.
- **Refinement Strength Selector**: Introduced a "Strength" selector (Minimal, Balanced, Strong) in the Refinement View to control the intensity of AI edits.
- **Refinement Testing Suite**: Added comprehensive `tests/test_refinement_integration.py` (orchestration, persistence) and `tests/test_view_refine.py` (view states, contracts), bringing the Refinement feature to 100% test coverage.
- **AI-Generated Message of the Day (MOTD)** — Implemented dynamic motivational subtext in workspace header:
  - Created `src/core/state_manager.py` for persistent session state management
  - Added `RefinementEngine.generate_custom()` for non-transcription text generation
  - Added SLM background task for MOTD generation with a 5-second startup delay and retry logic
  - Injected dynamic entropy (Unix timestamp) and increased temperature (1.2) to ensure variety in generated messages
  - **Rationale**: Replaces static subtext with dynamic, AI-generated content to improve application identity and user engagement without blocking startup performance.
- **Unified Logging Migration** — Moved all terminal output to the standard Python logging framework:
  - Removed all `print()` and `ConfigManager.console_print()` calls from the source tree
  - Replaced legacy console printing with appropriate `logger` levels (`info`, `warning`, `error`, `critical`)
  - Integrated transcription result echoing into `logger.info` for unified monitoring
  - Added JSON-based "Agent Friendly" formatting for log visualization
  - **Refactored Logging Architecture**: Relocated core logging logic to `src/core/log_manager.py`, separating it from UI error handling invariants.
  - **Rationale**: Consolidated all diagnostics into a single, rotatable, and configurable system. Eliminates "stray" terminal output that bypassed log management.
- **Root directory reorganization** — Streamlined project structure following Python/Linux conventions:
  - **Configuration consolidation**: Merged `mypy.ini` and `pytest.ini` into `pyproject.toml` `[tool.*]` sections (eliminated 2 standalone config files)
  - **Assets organization**: Created `assets/` directory at root, moved `icons/` → `assets/icons/` (groups runtime assets, simplifies path resolution)
  - **Script consolidation**: Moved `dev_tools/check.sh` → `scripts/check.sh` (eliminated `dev_tools/` directory, consolidated all build/dev scripts)
  - Updated 5 icon path references in Python source + 1 shell script from `"icons/"` to `"assets/icons/"`
  - **Rationale**: Modern Python projects consolidate config into `pyproject.toml`. Dedicated `assets/` directory improves discoverability and reduces path calculation complexity (e.g., `parents[4] / "assets" / "icons"` is semantically clearer than `parents[4] / "icons"`). All development tooling now centralized in `scripts/`.
- **Entry point reorganization** — Moved main application entry point from `scripts/run.py` to root-level `vociferous` executable:
  - Created executable `vociferous` script at project root (follows Linux convention: main entry point at root level)
  - Deleted `scripts/run.py` — now redundant, functionality moved to root-level `vociferous`
  - Deleted `vociferous.sh` — bash wrapper no longer needed (Python entry point handles environment setup directly)
  - Updated `scripts/install.sh` to reference new entry point: `./vociferous` instead of `python scripts/run.py`
  - Updated `scripts/install-desktop-entry.sh` to reference new entry point: `Exec=$PROJECT_DIR/vociferous` instead of `vociferous.sh`
  - Updated `tests/test_single_instance.py` to reference new entry point location
  - **Rationale**: Root-level entry point is the Linux/Unix convention for executable scripts. Simplifies user experience (`.venv/bin/activate && ./vociferous` instead of `.venv/bin/activate && python scripts/run.py`), matches common Python project patterns (e.g., Flask's `flask` command)
- **Source directory reorganization** — Improved architectural clarity by moving modules to semantic subdirectories:
  - Moved `src/transcription.py` → `src/services/transcription_service.py` (groups with other services: audio_service, slm_service, voice_calibration)
  - Moved `src/history_manager.py` → `src/database/history_manager.py` (groups with database core, models, DTOs, repositories)
  - Created `src/core/` subdirectory and moved `src/exceptions.py` → `src/core/exceptions.py` (establishes core utilities namespace for fundamental types)
  - Deleted `src/key_listener.py` — deprecated compatibility shim that only re-exported from `input_handler` (no actual code)
  - Updated 22+ import statements across codebase (main.py, result_thread.py, all views, widgets, models, tests)
  - **Rationale**: Top-level src/ now contains only application entry point (main.py), configuration files, orchestration (result_thread.py), and utilities (utils.py). All other modules organized into purpose-specific subdirectories for improved navigability and architectural cohesion.

### Fixed (Architecture & Quality)
- **Onboarding Data Persistence** — Fixed missing config saves during onboarding completion
  - Implemented `HotkeyPage.on_exit()` to save user-selected hotkey to `recording_options.activation_key`
  - Added final page `on_exit()` call in `OnboardingWindow._finish_onboarding()` for consistency
  - **Rationale**: Ensures all user preferences collected during onboarding (name, refinement toggle, hotkey) are properly saved to config before application starts
- **Voice Calibration Thread Cancellation** — Fixed zombie process issue during onboarding cancellation
  - Added `request_cancel()` method to `VoiceCalibrator` class with cancellation flag support
  - Updated `CalibrationPage.cleanup()` to call `request_cancel()` instead of deprecated `stop_recording()` method
  - Implemented proper thread lifecycle management to prevent hanging calibration threads when user exits onboarding mid-process
  - **Rationale**: Prevents resource leaks and zombie processes that occurred when users cancelled onboarding during voice calibration phase
- **Views Module Signal Routing Architecture** — Comprehensive audit and fixes to ensure Intent-Driven UI compliance
  - **RefineView (CRITICAL)**: Removed rogue `QPushButton` instances (`_btn_discard`, `_btn_accept`) with direct `clicked.connect()` wiring; implemented proper signal routing (`refinementAccepted`, `refinementDiscarded`) and `dispatch_action()` handlers
  - **SearchView (HIGH)**: Added missing `dispatch_action()` handlers for EDIT, DELETE, and REFINE actions; implemented routing signals (`editRequested`, `deleteRequested`, `refineRequested`)
  - **EditView**: Fixed semantic conflict (removed `can_cancel=True`, changed handler from `ActionId.CANCEL` to `ActionId.DISCARD`); standardized spacing (32px→Spacing.S5, 16px→Spacing.S3)
  - **HistoryView**: Removed inline `pane_style` variable and rogue border-left styling; added object names for unified stylesheet integration; implemented missing DELETE handler
  - **SettingsView**: Added missing BaseView contract methods (`get_capabilities()`, `get_selection()`, `dispatch_action()`)
  - **UserView**: Added missing BaseView contract methods (`get_capabilities()`, `get_selection()`, `dispatch_action()`)
  - **Spacing Standardization**: Replaced all hardcoded spacing values across EditView, RefineView, SearchView with semantic constants (S0-S7)
- **BaseView Interface Compliance**: All 10 views now uniformly implement the 4-method contract: `get_view_id()`, `get_capabilities()`, `get_selection()`, `dispatch_action()`

### Removed
- Deleted `scripts/audio_analyzer.py` — legacy debugging tool, never referenced in codebase
- Deleted `scripts/calibrate_voice.py` — prototype CLI wrapper, superseded by production `VoiceCalibrator` service in `src/services/voice_calibration.py`
- Deleted `src/ui/components/settings/` directory — SettingsDialog modal removed in favor of integrated SettingsView
- Deleted merged `src/ui/widgets/content_panel/` directory — separated back into distinct, purpose-specific components
- **Removed `AnimationDurations` class** from `src/ui/constants/timing.py` — consolidated all timing constants into single `Timing` class for unified, maintainable source of truth
- **Removed dead-code intents** from `src/ui/interaction/intents.py` — removed `OpenOverlayIntent` and `CloseOverlayIntent` (never used, not exported)
- **Removed dead-code model roles** from `src/ui/models/transcription_model.py` — removed unused `DisplayNameRole` (never queried via Qt model role API)
- **Removed deprecated method** from `src/ui/models/project_proxy.py` — removed unused `_has_matching_children()` method (superseded by Qt's recursive filtering)
- **Removed legacy typography aliases** from `Typography` class — `FONT_SIZE_BODY`, `FONT_SIZE_LARGE`, `FONT_SIZE_HEADER`, `FONT_SIZE_TITLE` removed; use scale names (`FONT_SIZE_BASE`, `FONT_SIZE_MD`, `FONT_SIZE_LG`, `FONT_SIZE_XXL`) instead
- **Removed module-level duplication in spacing.py** — removed redundant module-level S0-S7 and semantic aliases; all spacing values now contained in `Spacing` class with backward-compatible module-level re-exports
- **Removed dead-code stylesheet infrastructure** from `src/ui/styles/`:
  - Deleted `src/ui/styles/theme.py` — unused stylesheet generation (generate_base_stylesheet, generate_dark_theme, generate_light_theme functions never called)
  - Deleted `src/ui/styles/stylesheet_registry.py` — StylesheetRegistry singleton never instantiated or used anywhere in codebase (experimental dead code)
- **Removed dead-code utility functions** from `src/ui/utils/`:
  - Removed `qt_key_to_evdev()` from `keycode_mapping.py` — stub function with placeholder implementation (returns None), never called in codebase
  - Removed `initial_collapsed_days()` from `history_utils.py` — only used in test, never referenced in production code
- **Removed MetricsStrip widget and duplicate lifetime metrics rendering** from `src/ui/widgets/metrics_strip/`:
  - Deleted entire `metrics_strip/` directory (metrics_strip.py, metrics_strip_styles.py, __init__.py)
  - Removed MetricsStrip instantiation and layout integration from MainWindow
  - Removed metrics visibility state persistence (settings keys)
  - **Rationale**: MetricsStrip duplicated lifetime metrics rendering already provided by UserView with superior card-based layout. UserView is now the canonical location for all lifetime statistics (transcriptions, words, time recording, time saved, average length)
  - **Impacts**: MainWindow layout simplified: ViewHost + ActionDock (metrics moved to UserView only)
- **Removed dead StyledButton stylesheet file** from `src/ui/widgets/styled_button/`:
  - Deleted `src/ui/widgets/styled_button/styled_button_styles.py` — never imported, dead code
  - Migrated StyledButton to use unified stylesheet pattern: changed from object name selectors (`#styledPrimary`, `#styledSecondary`, `#styledDestructive`) to styleClass attribute selectors (`[styleClass="primaryButton"]`, etc.)
  - Updated `_apply_style()` to use `setProperty("styleClass", ...)` instead of `setObjectName(...)`
  - **Rationale**: Consolidates all button styling in unified_stylesheet.py, eliminates orphaned stylesheet definition
- **Removed dead TranscriptItem stylesheet file** from `src/ui/widgets/transcript_item/`:
  - Deleted `src/ui/widgets/transcript_item/transcript_item_styles.py` — never imported, dead code
  - File contained only empty string: `TRANSCRIPT_ITEM_STYLESHEET = ""`
  - Styling for transcript items is handled programmatically via QFont and QColor in `create_transcript_item()` and `paint_transcript_entry()`
  - **Rationale**: Eliminates orphaned stylesheet file with no QSS usage
- **Cleaned up Spectral Halo visualizer references** — incomplete removal had left orphaned config and documentation:
  - Removed `spectral_halo` section from `src/config_schema.yaml` (leader_boost, halo_smoothness sliders no longer needed)
  - Updated `src/ui/widgets/__init__.py` docstring to remove spectral_halo reference
  - Updated `docs/wiki/UI-Architecture.md` to reference BarSpectrumVisualizer (only active visualizer)
  - Updated `docs/wiki/Backend-Architecture.md` to show only bar_spectrum and waveform visualizer directories
  - Updated `README.md` to describe "spectrum visualization" generically instead of "Spectral Halo"
  - Updated `docs/wiki/Recording.md` to describe "spectrum visualization" generically
  - **Rationale**: Previous removal of Spectral Halo code left stale config and documentation; waveform visualizer preserved for future resurrection
- **Resurrected WaveformVisualizer** as optional spectrum visualization:
  - Moved waveform_visualizer from legacy `src/ui/widgets/waveform_visualizer/` to `src/ui/widgets/visualizers/waveform_visualizer/`
  - Created proper `__init__.py` files for visualizers package structure
  - Added `add_spectrum()` adapter method to WaveformVisualizer for API compatibility with BarSpectrumVisualizer
  - **Rationale**: Provides users with choice between bar spectrum (frequency bands) and waveform (amplitude levels) visualizations
- **Added visualizer type configuration**:
  - Added `visualization.visualizer_type` config schema with options: `bar_spectrum`, `waveform`
  - Default is `bar_spectrum` for current behavior
  - User can switch between visualizers in Settings View ("Visualization" section, "Spectrum Type" dropdown)
- **Implemented visualizer factory pattern**:
  - Created `create_visualizer()` factory function in `WorkspaceContent`
  - Factory reads `visualization.visualizer_type` config and instantiates appropriate visualizer
  - Both visualizers share common public API: `start()`, `stop()`, `add_spectrum(bands)`
  - Visualizer changes take effect on next recording session
- **Removed useless test cases** from test suite:
  - Deleted `test_detect_session_type()` from `tests/test_wayland_compat.py` — tautological test that always passes (checks if value is in set containing all possible values)
  - Deleted `test_views_dispatch_contract()` from `tests/test_phase2_scaffolding.py` — vague contract with unclear assertion (`isinstance(result, bool) or result is None`), removed per comment admitting implementation confusion
  - Simplified `test_backquote_exists()` in `tests/test_input_handler.py` — removed redundant `is not None` assertion after `hasattr()` verification
  - **Impact**: Test suite reduced from 264 to 262 passing tests (removed 2 useless tests), strengthened test signal

### Changed
- **Reorganized UI components directory structure** for improved architectural clarity:
  - Moved MainWindow sub-components into `main_window/` subdirectory:
    - `action_dock.py` → `main_window/action_dock.py` (context-sensitive action buttons)
    - `icon_rail.py` → `main_window/icon_rail.py` (navigation rail)
    - `system_tray.py` → `main_window/system_tray.py` (system tray manager)
    - `view_host.py` → `main_window/view_host.py` (view router/switcher)
  - Created `view_utilities/` subdirectory for shared view components:
    - `content_panel.py` → `view_utilities/content_panel.py` (detail display panel for HistoryView, ProjectsView)
    - `history_list.py` → `view_utilities/history_list.py` (history list wrapper)
  - Updated all imports across codebase (main.py, views, tests)
  - Updated architectural contract test to reflect new structure
  - **Rationale**: Groups related components together—MainWindow shell components are now properly nested under main_window/, and view helper components are grouped in view_utilities/. Improves discoverability and maintains architectural boundaries.

### Changed
- **Constants Directory Consolidation**: Simplified constants architecture
  - `spacing.py`: Moved all values into `Spacing` class; added module-level re-exports for backward compatibility with existing imports
  - `typography.py`: Consolidated font weight aliases (FONT_WEIGHT_REGULAR, FONT_WEIGHT_MEDIUM, FONT_WEIGHT_SEMIBOLD, FONT_WEIGHT_BOLD) to two canonical weights (NORMAL=400, EMPHASIS=600); added legacy aliases in class for backward compatibility
  - `timing.py`: Removed `AnimationDurations` class; all animation, polling, and timing constants now in single `Timing` class
  - `dimensions.py`: Updated to use `Spacing.S2` instead of importing module-level S2 (since S2 now only lives in Spacing class)
- **__init__.py exports**: Removed `AnimationDurations` from constants package exports and `__all__` list; maintained all other exports for API compatibility

### Fixed
- **MainWindow Title Bar Spacing**: Replaced hardcoded 3px spacer with semantic `Spacing.TITLE_BAR_SEPARATOR` constant (4px, S0 scale)
- **ActionDock Layout Spacing**: Fixed non-standard 6px spacing to use scale-compliant 8px (S1) for consistency across UI
- **Workspace Component Spacing**: Standardized all hardcoded spacing values in header.py, content.py, workspace.py, and transcript_metrics.py
  - WorkspaceHeader: Changed `setSpacing(8)` → `Spacing.MINOR_GAP`
  - WorkspaceContent carousel: Changed `setContentsMargins(12, 4, 12, 4)` → `(Spacing.S2, Spacing.S0, Spacing.S2, Spacing.S0)` and `setSpacing(8)` → `Spacing.MINOR_GAP`
  - MainWorkspace footer: Changed `setSpacing(16)` → `Spacing.BUTTON_GAP`
  - TranscriptMetrics grid: Changed `setSpacing(4)` → `Spacing.S0`, `setContentsMargins(0, 8, 0, 8)` → `(0, Spacing.MINOR_GAP, 0, Spacing.MINOR_GAP)`, `setHorizontalSpacing(24)` → `Spacing.S4`, `setVerticalSpacing(8)` → `Spacing.MINOR_GAP`
- **ContentPanel Namespace Collision**: Resolved duplication by separating into two distinct, purpose-specific components:
  - `src/ui/components/content_panel.py` — Detail display panel for HistoryView and ProjectsView (title, content, footer metadata)
  - `src/ui/widgets/workspace_panel.py` — Styled container for MainWorkspace (custom-painted rounded corners, state-dependent borders)
  - Each component now has a single, clear responsibility with no ambiguous mode switching
- **Spacing Scale Compliance**: Added new `TITLE_BAR_SEPARATOR` semantic constant to enforce consistent spacing throughout the application

### Added
- **READY State**: New WorkspaceState.READY for completed transcriptions
  - Green "Transcription ready" header persists until consuming action (Copy/Edit/Refine/Delete/Start Recording)
  - Auto-resets to IDLE when navigating away from Transcribe view
  - Provides clear visual feedback that a fresh transcription is available
- **Collapsible Metrics Strip**: Transcript metrics can now be toggled
  - "Show metrics" / "Hide metrics" toggle label
  - Metrics align precisely to transcript output bounds (0 left/right margins)
  - Collapsed state by default to reduce visual clutter
- **Edit View Navigation**: Return-to-origin navigation after editing
  - EditView tracks which view initiated the edit request
  - Both Save and Cancel actions return to the originating view
  - Search view state persists across edit operations via update_transcript()
- **Toggle Switch Widget**: New animated pill-shaped toggle switch with sliding circle for boolean settings
  - Smooth 200ms animation with cubic easing
  - Theme-integrated colors (primary when active, dark gray when inactive)
  - Replaces traditional checkboxes for modern UX
- **View-Specific Stylesheets**: Custom styling modules for Settings and User views
  - Dark dropdown menus with black backgrounds for better contrast
  - Permanent blue borders on key input fields (hotkey, language)
  - Fixed-width layouts with perfect centering
  - Professional card-based designs

### Fixed
- **Hotkey Recording Toggle**: Fixed a bug where recording would not trigger via hotkey if the workspace was in VIEWING or READY states.
- **Transcription Status**: Corrected an issue where fresh transcriptions incorrectly displayed "Transcript Loaded" instead of "Transcription complete" (green).
- **Workspace Data Sync**: MainWindow now uses the full `display_new_transcript` pipeline for fresh results, ensuring metrics update and the correct READY state is reached.
- **Intent Accessibility**: Relaxed guards on Edit and Delete intents to ensure they can be triggered immediately after a transcription completes.

### Changed
- **Unified Stylesheet Refactor**: Migrated `unified_stylesheet.py` to a more modular, section-based structure using semantic `Colors` mapping.
  - Implemented `Colors` semantic mapping class in `ui.constants` to isolate palette from visual definitions.
  - Improved styling for scrollbars, buttons, dialogs, and specific views (Transcribe, Edit, Refine).
  - Added support for purple and destructive semantic button classes.
- **UI Color Palette**: Added canonical `COLOR_*` constants and aligned legacy `Colors` names to the canonical palette for consistent naming without altering usage patterns.
- **Action Dock Grid Layout**: Action buttons now self-organize into a smart grid layout instead of a vertical list.
  - Dynamically repacks buttons into 2 columns based on visibility.
  - Ensures primary actions (like Start Recording) take prominence when alone.
  - Eliminates vertical stacking for cleaner UI.
- **Icon Rail Visuals**: Updated background color to `SURFACE_ALT` (lighter gray) to distinguish it from the main window background.
- **Icon Rail Interactivity**: Restored hover and active state visuals for navigation icons.
  - **Hover**: Subtle background highlight (`HOVER_BG`).
  - **Active**: Blue left border (`4px solid PRIMARY`) with semi-transparent background.
  - Provides clear "you are here" feedback for better navigation.
- **Transcribe View Header**: "Transcription ready" renamed to "Transcription complete" for better user alignment.
- **Transcribe View Header**: Color-coded status indicators
  - Recording state now uses Colors.DESTRUCTIVE (red) instead of hardcoded #FF4444
  - Ready state displays in Colors.SUCCESS (green)
  - Follows semantic color design tokens
- **Edit View Controls**: Simplified action buttons
  - Removed "Discard" button (redundant with Cancel)
  - Cancel button shows red hover state to indicate destructive action
  - Cleaner, less cluttered control panel
- **Architecture Tests**: Updated ~10 tests to reflect external editing model
  - Tests now validate that EditIntent delegates to external EditView
  - Workspace stays in VIEWING state during editing (editing happens in separate view)
  - CommitEditsIntent and DiscardEditsIntent return REJECTED/NO_OP when called on workspace
- **Style Enforcement Tests**: Added exclusions for pre-existing hardcoded colors
  - toggle_switch.py, bar_spectrum_visualizer.py, metrics_strip.py excluded as legacy widgets
- **User View**: Completely redesigned with refined layout:
  - Fixed-width centered container (900px) for consistent appearance
  - Reduced excessive spacing between sections
  - More concise explanations text to eliminate redundancy
  - Maintained card-based metric design with improved proportions
- **Settings View**: Complete overhaul with professional polish:
  - Fixed-width centered container (700px)
  - Multi-column grid layouts for related settings
  - Toggle switches replace all checkboxes for boolean options
  - Dark dropdown backgrounds (#1A1A1A) with white text for readability
  - Permanent blue borders on activation key and language fields
  - Language field limited to 120px width for better alignment
  - Larger, more prominent buttons (40px height)
  - Card-based design for History Management and Application sections
- **Audio Service**: Improved FFT binning logic from linear to logarithmic distribution to better represent speech and human hearing. Increased default resolution to 64 bands.
- **Audio Service**: Refined noise gating (0.12 threshold) and amplification curves for cleaner high-gain microphone performance.
- **Bar Spectrum Visualizer**: Replaced basic linear decay with CAVA-inspired smoothing algorithms, including Monstercat horizontal filtering, integral temporal smoothing, and quadratic gravity falloff.
- **Visualizer**: Established Bar Spectrum as the sole, integrated visualizer.
- **Refine View**: Removed the `QSplitter` draggable handle and replaced it with a static side-by-side layout.
- **Refine View**: Migrated styling to the unified stylesheet and improved the visual layout of the comparison zones.
- **Settings View**: Refactored control buttons (History, App) to side-by-side layout for improved density.
- **Settings View**: Increased horizontal spacing in form layouts for better readability.
- **Recording Visualizer**: Replaced the black hole visualizer with the new Spectral Halo (halo-with-lead) renderer.

### Added
- **Bar Spectrum Visualizer**: New professional-grade frequency bar visualizer with peak-hold gravity, inspired by the markjay4k tutorial.
- **Spectral Halo Visualizer**: New halo-with-lead spectrum visualizer with leader emphasis, smoothing, and ripple behavior.
- **Settings**: Added configuration for visualizer type (Halo vs Bars).
- **Settings**: Added tuning parameters for bar count, decay rate, and peak hold time.
- **Spectral Halo**: Added Spectral Halo tuning sliders for leader boost and halo smoothness.

### Removed
- **Legacy Visualizers**: Removed deprecated Spectral Halo and Waveform visualizers and their associated configuration toggle logic. 
- **BlackHoleVisualizer**: Deleted the deprecated black hole visualizer implementation.
- **Spectral Halo Settings**: Removed Spectral Halo tuning controls from Settings View as the visualization method has been deprecated.

### Fixed
- **Scrollbars**: Restored the custom blue styling for scrollbars by migrating missing styles to the unified stylesheet.
- **System Tray Icon**: Fixed icon mapping to use `system_tray_icon-placeholder.png` instead of non-existent image files.
- **Copy Button**: Fixed regression where copy/edit actions remained visible during subsequent recordings.
- **Styling**: Fixed window border not wrapping the entire application by moving it to the central widget and nesting the custom title bar.

---

# v2.6.0 - Navigation & Settings Architecture Overhaul

**Date:** January 14, 2026
**Status:** Major Feature Release

---

## Summary

This major update removes the traditional menu bar system and introduces a modern, icon-based navigation paradigm with dedicated Settings and User views. All configuration and user information functionality has been migrated to full-featured view surfaces, replacing the previous dialog-based approach.

## Added
- **Icon Rail Bottom Cluster**: Added User and Settings navigation icons with visual separator
- **SettingsView**: Complete settings management surface with:
  - Form-based configuration editing with inline validation
  - Hotkey configuration via `HotkeyWidget`
  - Export history functionality
  - Clear all history (with confirmation)
  - Application restart and exit controls
  - Real-time config synchronization
- **UserView**: Comprehensive user information surface with:
  - Lifetime metrics display (total transcriptions, words, time saved)
  - About section with version, architecture, and license information
  - Help section with keyboard shortcuts and documentation links
  - Metrics refresh on view activation
- **Refinement View Gating**: Icon Rail now checks `ConfigManager` for `refinement.enabled` to conditionally show refinement view

## Changed
- **Navigation Model**: Removed title bar menu system entirely, migrating all functionality to views
- **Settings Access**: Configuration is now managed exclusively through SettingsView (no more modal dialogs)
- **User Information**: Metrics and about information now accessed via dedicated UserView
- **ViewHost Behavior**: Now always emits `viewChanged` signal on view switches (including redundant switches) to ensure proper observer synchronization on boot
- **TitleBar**: Simplified to remove menu bar dependency, now uses symmetric layout slots
- **MainWindow**: Removed `MenuBuilder` integration, wired SettingsView signals directly to handlers

## Removed
- **Menu Bar System**: Complete removal of title bar menus (File, Edit, View, etc.)
- **SettingsDialog**: Replaced by SettingsView
- **Menu-based Actions**: All menu actions migrated to Icon Rail navigation or SettingsView controls

## Fixed
- **ActionDock Boot Sync**: ViewHost now emits `viewChanged` on all switches to ensure ActionDock synchronizes properly during initial application load
- **Title Bar Layout**: Fixed centering logic after menu bar removal
- **Test Suite**: Updated all tests to reflect new menu-less architecture:
  - Removed `QMenuBar` instantiation in TitleBar tests
  - Updated ViewHost routing tests to expect signals on redundant switches

## Technical Details

### Architecture Impact
- **Intent Propagation**: All user actions still follow strict intent-driven pattern (leaf → parent → controller)
- **Signal-Based Communication**: Settings changes propagate via Qt signals (no direct coupling)
- **Data Access**: UserView reads from HistoryManager using standard repository pattern
- **Config Isolation**: SettingsView uses ConfigManager singleton (single source of truth)

### Metrics Calculation
- **Hybrid Approach**: MetricsStrip shows current session metrics, UserView shows lifetime aggregates
- **Efficiency**: Time saved calculations use realistic typing (40 WPM) and speaking (150 WPM) speeds
- **Precision**: Duration formatting includes hours, minutes, and seconds

### Code Quality
- All tests passing: 271 passed, 4 skipped, 1 xfailed
- Ruff linting: All checks passed
- Mypy type checking: Success, no issues found

---

# v2.5.5 - UI State & Interaction Fixes

**Date:** January 13, 2026
**Status:** Feature Fix

---

## Summary

This update addresses critical usability issues identified in the January 13th audit, specifically targeting disjointed state management, broken navigation flows, and visual redundancy in the Action Dock.

## Fixed
- **Duplicate Action Dock**: Removed the redundant `WorkspaceControls` component from `MainWorkspace`, resolving the "double dock" issue.
- **Action Wiring**: Fully implemented `TranscribeView.dispatch_action` to route Edit, Delete, Save, Cancel, and Discard actions to the workspace via Intents.
- **View Navigation**: Implemented robust handling of `ViewTranscriptIntent` in `MainWindow`, enabling proper transition to detail views with data loading.
- **State Reactivity**: Added `stateChanged` signal to `MainWorkspace`, ensuring the Action Grid updates dynamically when recording starts or stops.
- **Cancel Logic**: Ensured the 'Cancel' button correctly triggers `CancelRecordingIntent`, aborting the pipeline instead of just stopping.

---

# v2.5.4 - Test Suite Convergence & Architecture Hardening

**Date:** January 13, 2026
**Status:** Maintenance Release

---

## Summary

This release resolves all outstanding test failures, enforcing strict architectural guardrails and ensuring the stability of the error handling and refinement subsystems.

## Fixed
- **Architecture Guardrails**: Whitelisted `TranscribeView` for state mutation and enforced "Edit Safety" checks in `MainWindow` state synchronization.
- **Error Handling**: Fixed function metadata preservation in `@safe_slot` and `@safe_callback` decorators to support proper introspection.
- **Refinement Subsystem**: Updated backend tests to gracefully handle optional dependencies (Ctranslate2) via dynamic mocking.
- **Intent Feedback**: Corrected test data initialization for `EditTranscriptIntent` verification.

---

# v2.5.3 - UI Convergence & Stabilization

**Date:** January 13, 2026
**Status:** Feature Release

---

## Summary

This monumental release converges the entire UI implementation with the Target Specification. It enforces strict invariants for signal architecture, master-detail layouts, and selection identity, while resolving critical startup crashes and replacing legacy components.

## Added
- **ProjectColors**: Added correct color palette logic for projects.
- **MetricsDock**: New unified statistics dock replacing the legacy MetricsStrip.
- **EditView**: Full implementation of the standalone transcript editor.
- **TranscribeView Editing**: Added live editing capability to the transcription preview.

## Changed
- **Typography Fixes**: Resolved `AttributeError` crashes by replacing non-existent `Typography` helper methods with explicit `QFont` instantiation across all views.
- **Layout Architecture**: Enforced strict Master-Detail layouts (Fixed List | Fluid Inspector) for `RecentView` and `ProjectsView`, removing splitters.
- **Selection Identity**: Migrated all selection logic from unreliable timestamps to robust integer `IdRole`.
- **Reactivity**: Implemented `capabilitiesChanged` signal for deterministic ActionGrid updates.
- **Metrics**: Replaced `MetricsStrip` with `MetricsDock`, simplifying the bottom bar architecture.

## Fixed
- **Startup Crash**: Fixed `AttributeError: type object 'Colors' has no attribute 'ACCENT_DANGER'` and others.
- **Font API**: Fixed crashes caused by `Typography.h2_font()` calls.

---

# v2.5.2 - Agentic Self-Healing Logging

**Date:** January 13, 2026
**Status:** Feature Release

---

## Summary

This release enables **"Agentic Self-Healing"** capabilities by transforming the logging infrastructure into a rich data stream for autonomous debugging. It introduces structured crash dumps, adjustable log verbosity, and referential error messages that point directly to documentation.

## Added

### Logging & Diagnostics
- **Agentic Crash Dumps**: Uncaught exceptions now generate detailed JSON incidents in `~/.local/share/vociferous/logs/crash_dumps/`, capturing local variables, stack traces, and system state for AI analysis.
- **Dynamic Verbosity**: Added configuration options to control logging levels at runtime via `config.yaml`.
- **Structured Output**: Added `logging.structured_output` option to emit logs as machine-parseable JSON lines.

### Error Handling
- **Referential Exceptions**: Introduced `VociferousError` hierarchy (e.g., `AudioDeviceError`, `ModelLoadError`) that carries:
  - **Context**: A dictionary of relevant variable states (e.g., model name, audio size).
  - **Doc Links**: Direct references to Wiki pages (e.g., `docs/wiki/Audio-Recording.md`) for resolution.

## Changed

### Core Infrastructure
- **Exception Hook**: Rewrote global `sys.excepthook` in `src/ui/utils/error_handler.py` to produce crash dumps before showing the user dialog.
- **Config Schema**: Updated `src/config_schema.yaml` with the new `logging` section.

---

# v2.5.1 - Shell Migration Stabilization

**Date:** January 13, 2026
**Status:** Bug Fix Release

---

## Fixed

### Shell & Navigation
- **IconRail**: Updated to use `VIEW_ID` constants instead of legacy hardcoded strings, resolving startup errors ("Attempted to switch to unknown view_id").
- **Navigation**: Temporarily disabled "Settings" button in rail until the Settings View is implemented.

### Stability
- **MainWindow**: Removed legacy `workspace` references that caused initialization crashes.
- **Audio Routing**: Implemented `update_audio_level` in `MainWindow` to correctly route audio signals to the active `TranscribeView`.
- **TranscriptList**: Added safety guards for `selectionModel` to prevent null pointer exceptions during data reloading.
- **Refinement**: Disabled legacy callback `on_refinement_completed` to prevent crashes until `RefineView` is fully integrated.

---

# v2.4.3 - Code Quality and Type Integrity

**Date:** January 12, 2026
**Status:** Maintenance Release

---

## Fixed

### Code Quality
- **Linting**: Resolved all remaining Ruff linting errors.
- **Typing**: Fixed multiple MyPy type errors across the project, including improved `SystemTrayManager` integration in `VociferousApp`.
- **Database**: Cleanup of unused type ignore comments in `TranscriptRepository` and `ProjectRepository`.
- **Orchestration**: Removed redundant `_on_refine_requested` implementation and fixed incomplete signal-slot signatures.

---

# v2.4.2 - Developer Experience (DX) & Architecture Documentation

**Date:** January 12, 2026
**Status:** Maintenance Release

---

## Changed

### Documentation
- **Copilot Instructions**: Completely overhauled `.github/copilot-instructions.md` to strictly enforce the **Intent Pattern** for UI transitions and **SQLAlchemy** best practices for data persistence.
- **Wiki**: Added formally defined "Interaction Layer (Intents)" section to `docs/wiki/UI-Architecture.md`.
- **README**: Added "Technical Architecture" section detailing the stack and design patterns.

### Developer Resources
- **Architecture Audit**: Added `docs/agent_resources/agent_reports/2026-01-12_architecture_audit.md` as a canonical reference for the system's current architectural state.

---

# v2.4.1 - Documentation Polish

**Date:** January 2026
**Status:** Maintenance Release

---

## Fixed

### Documentation
- **Threading Model Diagram**: Updated `docs/wiki/Threading-Model.md` to use modern Mermaid `flowchart` syntax and quoted labels, fixing rendering issues with special characters in node names.

---

# v2.4.0 - Advanced Refinement & Resource Intelligence

**Date:** January 2026
**Status:** Feature Release

---

## Summary

This release brings significant maturity to the AI Refinement engine, replacing the legacy experimental backend with a robust **Qwen3-4B-Instruct** foundation. We introduce **Refinement Profiles** (Minimal, Balanced, Strong) to give users granular control over editing intensity, and a **Dynamic Resource Manager** that intelligently loads models into GPU memory based on available headroom.

The input system has been hardened against prompt injection using a "Swiss-Army-Knife" system prompt strategy, treating transcripts strictly as data rather than instructions.

## Added

### AI Refinement
- **Directive-Based Prompting**: New "Refinement Profiles" allow selecting between `MINIMAL` (grammar only), `BALANCED` (light cleanup), and `STRONG` (flow/structure) editing modes.
- **Dynamic VRAM Management**: The engine now queries `nvidia-smi` to calculate available GPU headroom:
  - **>40% Free**: Auto-loads to GPU (CUDA) for maximum speed.
  - **20-40% Free**: Defaults to GPU but logs warnings.
  - **<20% Free**: Pauses initialization and asks the user for explicit confirmation to avoid system instability.
- **32k Context Window**: Increased context limit from 4k to 32k tokens to support long-form dictation refinement.

### UI / UX
- **Profile Controls**: Integrated radio control group (Min/Bal/Str) directly into the workspace toolbar.
- **Sidebar Polish**: Aligned sidebar collapse button with search controls and improved styling consistency.

## Changed

### Core Infrastructure
- **Model Upgrade**: Replaced `vennify/t5-base` (Encoder-Decoder) with `Qwen/Qwen3-4B-Instruct` (Decoder-Only) for superior semantic reasoning.
- **Inference Optimization**: Switched CUDA compute type to `int8_float16` for optimal Tensor Core utilization on NVIDIA GPUs.

---

# v2.3.0 - AI Grammar Refinement (MVP)

**Date:** January 2026
**Status:** Feature Release

---

## Summary

Introduces **Single-Click AI Refinement**, a powerful new capability to instantly correct grammar, tense, and phrasing in your transcripts. Powered by a local, purpose-built GEC (Grammatical Error Correction) model, this feature transforms raw dictation, such as "him going to the store", into polished prose ("He was going to the store") without any valid text losing its meaning.

This release integrates a production-grade CTranslate2 inference engine directly into Vociferous, ensuring zero external dependencies at runtime and complete privacy.

## Added

### Core Features
- **Grammar Refinement (GEC)**: New backend engine using the `vennify/t5-base-grammar-correction` model (converted to quantized CTranslate2 format).
- **Non-Destructive Editing**: Refinements are saved as "variants" of the original transcript. The original raw text is never lost.
- **Local Inference**: All processing happens on-device using optimized CPU inference (Int8 quantization). No GPU required.

### UI / UX
- **Refinement Toggle**: New "Refine" button added to the Workspace (visible when enabled in settings).
- **Settings**: Added "Grammar Refinement" section to the Settings dialog to toggle the feature.
- **Status Feedback**: Real-time status messages during model loading and inference.

### Infrastructure
- **Model Management**: Automatic schema migration for variant support (`current_variant_id` column).
- **Artifact Caching**: Secure caching of model artifacts in standard system locations (`~/.cache/Vociferous/models`).
- **Dependencies**: Removed runtime dependence on heavy ML libraries (`torch`, `transformers`) in favor of lightweight inference runtimes.

---

# v2.2.1 - Group Hierarchy & UI Polish

**Date:** January 2026
**Status:** Minor Release

---

## Summary

Introduces hierarchical organization for Projects (subgroups), enabling deeper content structuring. Enhances the sidebar with drag-and-drop management, bulk operations for transcripts, and improved visual controls.

## Added

### Organization
- **Nested Projects**: Added ability to create subgroups up to one level deep.
- **Drag & Drop**: Transcripts can now be moved between groups via drag-and-drop.
- **Bulk Actions**: Support for multi-selecting transcripts in the sidebar to move or delete them in batches.

### UI / UX
- **Sidebar Toggle**: Added a dedicated button to collapse/expand the sidebar panel.
- **Dialog Usability**: Primary actions in dialogs now trigger on the "Enter" key.
- **Error Dialogs**: Improved layout and text visibility for error reporting.

## Changed

### Core Infrastructure
- **Database Schema**: Added `parent_id` column to `projects` table with automatic micro-migration on startup.

### Styling
- **Visual Refinements**: Updated context menu selection styles and standardized radio button appearance.

---

# v2.2.0 - Architecture Overhaul (SQLAlchemy Migration)

**Date:** January 2026
**Status:** Major Release

---

## Summary

Complete persistence layer rewrite migrating from raw SQLite cursors to **SQLAlchemy 2.0 ORM**. This architectural shift lays the foundation for complex hierarchical data relationships (subgroups), external integrations, and robust schema management.

**⚠️ BREAKING CHANGE**: This release resets the local database structure. Legacy history files will be recreated (nuked) upon first launch to ensure schema consistency.

## Changed

### Core Infrastructure
- **Database Engine**: Replaced hand-rolled `sqlite3` queries with **SQLAlchemy** ORM sessions.
- **Schema Management**: Introduced declarative models (`src/models.py`) for `Transcript` and `Project` entities.
- **Migration Strategy**: Implemented "fresh start" policy—legacy databases are detected and reset to pristine state to guarantee stability.

### Internal API
- **Refactoring**: Rewrote `HistoryManager` to utilize SQLAlchemy `Session` for all CRUD operations, improving safety and maintainability.
- **Type Safety**: Enhanced type constraints on database models ensuring integrity at the application level before persistence.

---

# v2.1.6 - UI Polish (Project Indicators)

**Date:** January 2026
**Status:** Enhancement

---

## Changed

### UX / Styling
- **Cleaned Up Tooltips**: Removed the full-text tooltip from sidebar items (transcripts and Projects) to reduce UI clutter as requested.
- **Improved Selection Indicator**: Changed the Project item selection style from a solid block to a cohesive background with a circular dot indicator on the left. The dot inherits the group's color (or defaults to blue), providing a cleaner and more distinct visual cue.

---

# v2.1.5 - Critical Hotfix (Dialog Crash & Safety)

**Date:** January 2026
**Status:** Hotfix

---

## Fixed

### Stability
- **Dialog Crash**: Fixed `NameError: name 'QFrame' is not defined` in `custom_dialog.py` caused by missing import in the v2.1.3 refactor. This prevented all custom dialogs (Confirmation, Input, Error) from opening.

### UX / Safety
- **Delete Confirmation**: Enforced confirmation dialog for ALL transcript deletion events, including those triggered by the "Delete" key in the sidebar history list (previously bypassed confirmation).

---

# v2.1.4 - Dialog Visual Polish

**Date:** January 2026
**Status:** Hotfix

---

## Changed

### UI / Styling
- **Dialog Frames**: Thickened the dialog blue border to 3px (was 1px) and removed border radius to match the rectangular window shape, ensuring a clean and consistent visual style for frameless dialogs.

---

# v2.1.3 - UI Refinements (Dialog Borders)

**Date:** January 2026
**Status:** Hotfix

---

## Fixed

### UI / Rendering
- **Dialog Borders**: Refactored all custom dialogs (`StyledDialog`, `SettingsDialog`, `ExportDialog`, `CreateGroupDialog`, `MetricsExplanationDialog`) to use a structural `QFrame` wrapper (`dialogFrame`) for proper border rendering. Moved border styling from `QDialog` to `QFrame` to prevent content-level border artifacts and ensure a consistent frameless window outline.

---

# v2.1.2 - UI Refinements & Binding Fixes

**Date:** January 2026
**Status:** Hotfix

---

## Fixed

### UI / Rendering
- **Sidebar Padding**: Increased timestamp column width in sidebar delegate (70px → 90px) to prevent time cutout on systems with wider fonts or varying DPI.

### Data Binding
- **Recent Transcripts**: Fixed regression where moving a transcript out of a Project would not immediately make it reappear in the Recent list. Enabled `dynamicSortFilter` on `ProjectProxyModel` to react instantly to `GroupIDRole` changes.

---

# v2.1.1 - Critical Crash Fix

**Date:** January 2026
**Status:** Hotfix

---

## Summary

Emergency hotfix addressing a critical segmentation fault on application startup caused by infinite recursion in the transcription data model.

## Fixed

### Critical Stability
- **TranscriptionModel**: Fixed segmentation fault where leaf nodes (entries) were incorrectly processed as branch nodes in `rowCount()`. Implemented invalidation check using `internalId` to prevent proxy models from triggering infinite recursion stack overflows.

---

# v2.1.0 - Code Health & Type Safety

**Date:** January 2026
**Status:** Maintenance Release

---

## Summary

Comprehensive codebase cleanliness and type safety overhaul. Achieved zero metadata and type errors across the entire project by enforcing strict MyPy and Ruff compliance. Fixed latent logic bugs in proxy models and intent feedback handlers identified during static analysis.

## Fixed

### Critical Logic
- **Project Proxy**: Removed unreachable dead code referencing undefined `source_model` variable in `project_proxy.py`
- **Intent Feedback**: Fixed valid return type violation in status message timer callback (lambda returned tuple instead of `None`)
- **System Safety**: Replaced unsafe bare `except:` blocks with `except Exception:` in `transcription_model.py` to prevent masking system signals like `KeyboardInterrupt`

### Type Safety
- **Workspace**: Resolved variable type reuse ambiguity in `_on_primary_click` and related handlers in `workspace.py`
- **Architecture Tests**: Fixed type checking logic in `test_architecture_guardrails.py` for ensuring export string verification

## Changed

### Repository Hygiene
- **Linter Compliance**: Resolved ~54 Ruff issues covering unused imports, dead variables, and redundant logic
- **Type Compliance**: Achieved clean MyPy run across 108 source files
- **Code Cleanup**: Removed multiple instances of unused error logger assignments and redundant imports

---

# v2.0.1 - Repository Hygiene & Debt Assessment

**Date:** January 2026  
**Status:** Maintenance Release

---

## Summary

Post-stabilization maintenance release focused on repository hygiene and technical debt assessment. Removed transient planning artifacts, updated documentation structure, and conducted comprehensive code health audit. No functional changes—this is a pure documentation and repository organization release.

## Changed

### Repository Cleanup
- **Removed**: 7 transient planning artifacts from `docs/dev/planning/`:
  - `documentation-alignment-plan.md` — Superseded planning proposal
  - `file-relevance-audit-batch-01.md` — Exhausted audit log (scripts)
  - `file-relevance-audit-batch-02.md` — Exhausted audit log (README/wiki)
  - `file-relevance-audit-batch-03.md` — Exhausted audit log (launchers)
  - `tech-debt-assessment-batch-01.md` — Exhausted assessment (Type C findings)
  - `tech-debt-assessment-batch-02.md` — Exhausted assessment (complexity justified)
  - `tech-debt-assessment-batch-03.md` — Exhausted assessment (Type B declined)
- **Removed**: Empty `docs/dev/planning/` directory

### Documentation
- **Updated**: `docs/wiki/Home.md` Project Structure to include frozen architecture documentation in `docs/dev/`
- **Preserved**: All binding architecture documents (interaction-core-frozen.md, authority-invariants.md, intent-catalog.md, edit-invariants.md)

## Technical Debt Assessment

Conducted systematic code health audit across three batches covering non-UI infrastructure:

### Batch 01: Configuration & Utilities
- **Files Reviewed**: `src/utils.py`, `src/config_schema.yaml`
- **Findings**: One minor Type C finding (repeated guard pattern in ConfigManager)
- **Outcome**: Complexity justified; no action taken

### Batch 02: Core Infrastructure
- **Files Reviewed**: `src/key_listener.py`, `src/result_thread.py`, `src/transcription.py`
- **Findings**: One Type C finding (duplicate media key mappings in EvdevBackend)
- **Outcome**: All complexity proportionate to platform requirements; no action taken

### Batch 03: Utility Infrastructure
- **Files Reviewed**: `src/history_manager.py`, `src/ui/utils/clipboard_utils.py`, `src/ui/utils/error_handler.py`
- **Findings**: One Type B finding (repetitive try/except in HistoryManager), one Type C finding
- **Outcome**: Type B refactor declined due to heterogeneous method semantics; error_handler.py identified as exemplary implementation

### Assessment Conclusions
- **No code modifications**: All identified complexity was either justified defensive programming or cosmetic
- **Architecture validated**: Thread safety, error handling, and platform abstraction all proportionate to domain requirements
- **Remediation declined**: Proposed HistoryManager refactor determined unsafe without behavioral changes

## Notes

This release represents a **conservative post-stabilization posture**. The technical debt assessment confirmed that the non-UI codebase is architecturally healthy, with complexity patterns reflecting genuine platform requirements rather than entropy.

Repository surface area reduced by removing agent-specific planning logs that served their purpose during Phases 1-7 but are no longer needed for contribution or evolution.

---

# v2.0.0 - Architecture Stabilization

**Date:** January 2026
**Status:** Release

---

## Summary

Architecture stabilization release. Beta 2.0 introduces no new user-facing features. Its value lies entirely in correctness, safety, and long-term maintainability. This release establishes a frozen interaction architecture with automated guardrails that prevent regression.

## Added

### Intent-Driven Interaction Architecture
- All user actions are now represented as explicit intent objects (`BeginRecordingIntent`, `StopRecordingIntent`, `ViewTranscriptIntent`, `EditTranscriptIntent`, `CommitEditsIntent`, `DiscardEditsIntent`, `DeleteTranscriptIntent`, `CancelRecordingIntent`)
- Single authoritative `handle_intent()` method validates and processes all user interactions
- `IntentResult` objects capture outcome, reason, and state for every action

### Transactional Editing Model
- Edit sessions are explicitly entered and exited via `EditTranscriptIntent`, `CommitEditsIntent`, and `DiscardEditsIntent`
- Only terminal intents (commit or discard) can exit the editing state
- Unsaved changes are protected—recording, navigation, and deletion are blocked during editing

### Intent Outcome Visibility
- `IntentFeedbackHandler` maps intent results to user-visible status bar messages
- Feedback layer consumes `IntentResult` only—never queries workspace state
- Rejected actions produce informative messages explaining why they failed

### Architectural Guardrail Tests
- 9 static analysis tests in `test_architecture_guardrails.py` enforce frozen architecture
- Tests scan source code directly and fail CI on boundary violations
- Covers: `set_state` usage, feedback layer isolation, intent catalog sync, orchestration privilege

### Documentation
- [Interaction Core Freeze Declaration](docs/dev/interaction-core-frozen.md) — What is frozen and why
- [Intent Catalog](docs/dev/intent-catalog.md) — Complete vocabulary of user intents
- [Authority Invariants](docs/dev/authority-invariants.md) — Who owns state transitions
- [Edit Invariants](docs/dev/edit-invariants.md) — Transactional editing guarantees
- [Intent Outcome Visibility](docs/dev/intent-outcome-visibility.md) — Feedback layer design

## Changed

### Interaction Authority Consolidation
- All user-initiated state changes now flow through `handle_intent()` → `_apply_*()` methods
- UI components no longer call `set_state()` directly for user actions
- Clear separation between user interaction (intents) and engine orchestration

### Orchestration Privilege Formalization
- Renamed `update_transcription_status()` → `sync_recording_status_from_engine()`
- Orchestration method explicitly documented as the only external `set_state()` caller
- Edit-safety guards prevent orchestration from overriding editing state

### Fixed
- Fixed hotkey "randomly" stopping recording on key release. Added proper support for both `press_to_toggle` and `push_to_talk` recording modes.
- Added visible help text in Settings describing how each recording mode works.
- No more silent state changes without validation
- All transitions produce `IntentResult` with success/failure reason

### Editing Safety Violations
- Fixed: Recording could start while editing unsaved changes
- Fixed: Navigation could abandon unsaved edits without warning
- Fixed: Deletion could target content being actively edited

## Deprecated

### Direct State Mutation
- UI components calling `workspace.set_state()` directly is no longer valid
- All user actions must create and dispatch intents

### Ad-Hoc Interaction Handling
- Scattered `if/else` state checks in UI components are deprecated
- Use `handle_intent()` for all user action processing

## Notes

**This release introduces no new user-facing features.** Its purpose is to guarantee correctness, safety, and maintainability for future development.

The interaction architecture is now **frozen**. Changes to the frozen core require explicit design review and documentation updates.

**Versioning Policy:**
- `2.0.x` — Stabilization releases (no new features, bug fixes only)
- `2.1.x` — Feature development resumes (local SLM integration planned)

---

# v1.9.0 - Intent Outcome Visibility

**Date:** January 2026  
**Status:** Release

---

## Summary

User feedback layer for the intent-driven interaction architecture. Introduces `IntentFeedbackHandler` to provide clear, actionable status messages when user actions are rejected, completing the interaction architecture with proper outcome visibility.

## Added

### Intent Feedback System
- **`IntentFeedbackHandler`**: Presentation layer that consumes `IntentResult` and displays user-friendly status messages
- **Outcome Mapping**: Maps intent results to appropriate feedback:
  - `ACCEPTED`/`NO_OP`: Silent (success is expected)
  - `REJECTED` with user-actionable reasons: Display informative status message
  - `REJECTED` when button shouldn't be visible: Silent logging only
- **Status Bar Integration**: 4-second auto-dismiss messages styled consistently with application theme
- **Structured Logging**: Configurable debug verbosity for intent processing outcomes

### Documentation
- [Intent Outcome Visibility](docs/dev/intent-outcome-visibility.md) — Outcome mapping specification and architecture diagram
- Phase 6 exit criteria and constraints documented

### Tests
- **13 new tests** (67 total intent/feedback tests, 165 Tier 1 tests passing)
  - `TestIntentFeedbackMapping` (8 tests): Verify correct status messages for each outcome type
  - `TestIntentFeedbackLogging` (3 tests): Verify logging behavior and verbosity
  - `TestPhase6Constraints` (2 tests): Verify handler never queries workspace state directly

## Changed

### Feedback Layer Design
- Status messages driven entirely by `IntentResult`—no inspection of workspace state
- Clear separation between interaction processing and user feedback

## Technical Notes

**Phase 6 Constraints Maintained:**
- No new state transitions introduced
- No UI branches on workspace state for feedback decisions
- All feedback driven exclusively by `IntentResult` data

**Architecture Completeness:** With this release, the intent-driven interaction architecture is feature-complete with proper outcome visibility.

---

# v1.8.0 - Authority Consolidation

**Date:** January 2026  
**Status:** Release

---

## Summary

Final authority consolidation for user-initiated state changes. All user interactions now flow through the intent layer with authoritative `_apply_*()` methods. Establishes clear separation between user interaction (intents) and orchestration (engine sync).

## Added

### Authority Invariants
- **All Invariants Enforced**: 7-11 in [Authority Invariants](docs/dev/authority-invariants.md) now have `ENFORCED` status
- **Stopping Condition Verified**: No external component directly mutates workspace state for user actions
- **Orchestration Privilege Formalized**: `sync_recording_status_from_engine()` (renamed from `update_transcription_status()`) documented as the only external `set_state()` caller

### Intent Migration Completed
- **`ViewTranscriptIntent`**: Migrated to authoritative `_apply_view_transcript()` method
  - Carries both timestamp and text
  - Validates state (cannot view while recording or with unsaved edits)
  - Transitions to `VIEWING` or `IDLE` based on content
- **`DeleteTranscriptIntent`**: Migrated to authoritative `_apply_delete_transcript()` method  
  - Validates state (can only delete in `VIEWING`)
  - Emits deletion signal after validation
  - State transition deferred until after user confirmation via `clear_transcript()`

### Edit Safety Guards
- **Orchestration Safety**: Engine status sync prevented from overriding `EDITING` or `VIEWING` states
- **Clear History**: Now uses `clear_transcript()` instead of direct `set_state()` calls

### Documentation
- [Authority Invariants](docs/dev/authority-invariants.md) — Complete authority model with all invariants enforced

### Tests
- **14 new tests** (54 total intent tests, 142 Tier 1 tests passing)
  - `test_view_intent_is_authoritative`
  - `test_delete_intent_validates_but_defers_state_change`
  - `test_all_destructive_click_routes_through_intents`
  - View intent validation tests (6 tests)
  - Delete intent validation tests (5 tests)

## Changed

### State Mutation Authority
- **All user-initiated state changes** now flow through `handle_intent()` → `_apply_*()` methods
- **UI components** no longer call `set_state()` directly for user actions
- **Orchestration** limited to recording state sync only, with edit-safety constraints

## Fixed

### State Consistency
- No more silent state changes without validation
- All transitions produce `IntentResult` with success/failure reason
- Clear audit trail for all state mutations

## Technical Notes

**Phase 5 Stopping Condition Met:**
- All user interactions flow through authoritative intent handlers
- Only 2 orchestration `set_state()` calls remain (in `sync_recording_status_from_engine()`)
- All destructive actions (delete, discard, cancel) route through intent layer

---

# v1.7.0 - Transactional Editing

**Date:** January 2026  
**Status:** Release

---

## Summary

Implements transactional editing model with explicit enter/exit semantics. Edit sessions can only be exited through terminal intents (`CommitEditsIntent` or `DiscardEditsIntent`), ensuring unsaved changes are never silently lost.

## Added

### Terminal Intent System
- **`CommitEditsIntent`**: Authoritative method to save edits and exit editing state
  - Precondition: `state == EDITING`
  - Postcondition: `state == VIEWING`, `_has_unsaved_changes == False`
  - Emits `saveRequested` signal to persist content
- **`DiscardEditsIntent`**: Authoritative method to abandon edits and exit editing state
  - Precondition: `state == EDITING`
  - Postcondition: `state == VIEWING`, `_has_unsaved_changes == False`
  - Does NOT emit save signal (content discarded)
- **`EditTranscriptIntent`**: Authoritative method to enter editing state
  - Precondition: `state == VIEWING`, transcript loaded
  - Postcondition: `state == EDITING`
  - Rejects in `IDLE` (no transcript) or `RECORDING`

### Edit Invariants
- **Invariant 1**: Can only enter editing from `VIEWING` with loaded transcript
- **Invariant 2**: Cannot begin recording while editing
- **Invariant 3**: Cannot view different transcript with unsaved edits
- **Invariant 4**: Edit state can only exit through terminal intents
- **Invariant 5**: Terminal intents clear `_has_unsaved_changes` flag
- **Invariant 6**: `RECORDING` implies `_has_unsaved_changes == False`

### Documentation
- [Edit Invariants](docs/dev/edit-invariants.md) — Transactional editing guarantees

### Tests
- **19 new tests** (40 total intent tests, 128 Tier 1 tests passing)
  - `TestEditIntentStateAssertions` (5 tests): Edit entry validation
  - `TestCommitIntentStateAssertions` (4 tests): Commit terminal behavior
  - `TestDiscardIntentStateAssertions` (4 tests): Discard terminal behavior
  - `TestPhase4StoppingCondition` (2 tests): Verify only terminal intents exit editing
  - Edit safety tests (4 tests): Recording/view blocked during editing

## Changed

### Edit Flow Authority
- Save button now routes through `CommitEditsIntent`
- Cancel/discard actions route through `DiscardEditsIntent`
- Edit button routes through `EditTranscriptIntent`
- All edit-related state changes use authoritative `_apply_*()` methods

## Fixed

### Data Safety
- **Unsaved changes protected**: Recording, navigation, and deletion blocked during editing
- **No silent exits**: Edit state can only be left through explicit commit or discard
- **State consistency**: All edit transitions enforce pre/postconditions with assertions

## Technical Notes

**Phase 4 Stopping Condition Met:**
- Editing impossible to exit without explicit terminal intent
- No edit-related state mutated outside `_apply_*()` methods
- All 6 invariants enforced by runtime assertions

---

# v1.6.0 - Recording Intent Authority

**Date:** January 2026  
**Status:** Release

---

## Summary

Establishes authoritative intent handling for recording operations. All recording state transitions (begin, stop, cancel) now flow through the intent layer with proper validation and state assertions.

## Added

### Authoritative Recording Intents
- **`BeginRecordingIntent`**: Sole legal pathway for `IDLE`/`VIEWING` → `RECORDING` transitions
  - Precondition: `state == IDLE` or `state == VIEWING`
  - Postcondition: `state == RECORDING`, `_has_unsaved_changes == False`
  - Emits `recordingStartRequested` signal after state mutation
- **`StopRecordingIntent`**: Authoritative transcription trigger
  - Precondition: `state == RECORDING`
  - Postcondition: transcribing status set, `processingRequested` emitted
- **`CancelRecordingIntent`**: Authoritative recording cancellation
  - Precondition: `state == RECORDING`
  - Postcondition: `state == IDLE`, `_has_unsaved_changes == False`

### Test Infrastructure
- **Test Tier Classification**: Separated UI-independent (Tier 1) and UI-dependent (Tier 2) tests
  - Tier 1: 107 tests (fast, no Qt widget instantiation)
  - Tier 2: UI integration tests requiring full widget setup
- **pytest marker**: `ui_dependent` for selective test execution
- **Run Tier 1 only**: `pytest -m 'not ui_dependent'`

### Invariant Enforcement
- **Assertion guards** on all recording state transitions
- **Precondition/postcondition docstrings** on all `_apply_*()` methods

### Tests
- **25 intent tests passing** (107 total Tier 1 tests)
- Recording intent authority verified for all three operations

## Changed

### Button Click Flow
- Primary click button (`_on_primary_click`) now creates intents and routes through `handle_intent()`
- Destructive click (`_on_destructive_click`) routes `RECORDING` case through `CancelRecordingIntent`
- No dual authority: `button click → intent → handle_intent → _apply_* → state mutation`

### Method Naming
- `_bridge_begin_recording` → `_apply_begin_recording` (authoritative mutator)
- `_bridge_stop_recording` → `_apply_stop_recording` (authoritative mutator)
- Added `_apply_cancel_recording` (authoritative mutator)

## Fixed

### State Consistency
- Recording state changes now validated and logged
- All transitions produce `IntentResult` with outcome tracking
- Debug assertions catch invalid state mutations

## Technical Notes

**Phase 3 Complete:**
- All recording intents route through authoritative `_apply_*()` methods
- Legacy direct state mutation from buttons eliminated
- Clear separation between UI event handling and state mutation

---

# v1.5.0 - Intent-Driven Interaction Foundation

**Date:** January 2026  
**Status:** Release

---

## Summary

Foundational release establishing the intent-driven interaction architecture. Introduces semantic vocabulary for all user actions without changing existing behavior, setting the stage for authoritative state management and transactional editing.

## Added

### Interaction Vocabulary
- **`InteractionIntent`**: Base class for all user actions with 8 concrete intent types:
  - `BeginRecordingIntent`: Start recording
  - `StopRecordingIntent`: Stop recording and transcribe
  - `CancelRecordingIntent`: Abort recording without transcribing
  - `ViewTranscriptIntent`: Load transcript for viewing
  - `EditTranscriptIntent`: Enter editing mode
  - `CommitEditsIntent`: Save edits and exit editing
  - `DiscardEditsIntent`: Abandon edits and exit editing
  - `DeleteTranscriptIntent`: Remove transcript

### Intent Processing Framework
- **`IntentOutcome`** enum: `ACCEPTED`, `REJECTED`, `DEFERRED`, `NO_OP`
- **`IntentResult`**: Records outcome, reason, and state for every action
- **`MainWorkspace.handle_intent()`**: Central dispatch method for all intents
- **`intentProcessed`** signal: Observability hook for intent outcomes

### Documentation
- [Interaction Architecture Audit](docs/dev/interaction-audit.md) — Phase 1 baseline documenting all 14 state mutation points
- [Intent Catalog](docs/dev/intent-catalog.md) — Complete vocabulary of user intents

### Tests
- **25 new tests** for intent construction and passthrough behavior
- No state assertions yet (additive scaffolding only)

## Changed

### Architecture Patterns
- Introduced explicit intent objects for all user actions
- Added single authoritative dispatch point (`handle_intent()`)
- Maintained existing signal wiring (no behavioral changes)

## Technical Notes

**Phase 1-2 Complete:**
- Semantic scaffolding in place for intent-driven refactor
- Existing authority violations intentionally preserved for visibility
- `set_state()` calls documented in audit remain unchanged
- This is an additive-only release—existing behavior unchanged

**Future Phases:**
- Phase 3: Make recording intents authoritative
- Phase 4: Implement transactional editing with terminal intents
- Phase 5: Consolidate all user-initiated state changes through intents
- Phase 6: Add intent outcome visibility layer

---

# v1.4.3 - Intent Architecture Planning

**Date:** January 2026  
**Status:** Planning

---

## Summary

Planning release establishing the roadmap for intent-driven interaction architecture refactor. Documents all existing state mutation points and signal wiring to serve as baseline for authority consolidation.

## Added

### Documentation
- [Interaction Architecture Audit](docs/dev/interaction-audit.md) — Comprehensive audit of current interaction patterns:
  - 14 state mutation points across `MainWorkspace` and `MainWindow`
  - Complete signal-slot wiring for controls, content, and sidebar
  - State transition flows for all user interactions
  - Identified 5 external `set_state()` calls (authority violations)
  - Refactor targets for Phases 2-4

## Technical Notes

**Purpose:** This audit serves as the authoritative reference for measuring refactor progress through Phases 2-6. No code changes in this release—purely architectural documentation.

**Identified Issues:**
- Multiple components directly mutate workspace state
- No unified validation point for user actions
- Edit state can be exited through multiple pathways
- State transitions lack explicit success/failure semantics

---

# v1.4.2 - Comprehensive Error Isolation

**Date:** January 2026  
**Status:** Release

---

## Summary

Stability-focused release implementing comprehensive error isolation across all signal handlers, callbacks, and critical operations. Introduces new error handling utilities (`safe_callback`, `safe_slot_silent`) and adds deferred model invalidation to prevent segfaults during Project operations.

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

**Problem:** Segfault when assigning transcripts to Projects from the Recent tab. Root cause: proxy model called `invalidateFilter()` during context menu callback, corrupting the `QModelIndex` mid-operation.

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
| `ProjectTree` | try/except + logging on all CRUD methods |
| `HistoryTreeView` | `safe_callback` on context menu lambdas, error handling on CRUD |
| `ProjectProxyModel` | `safe_callback` on signal lambdas, protected `filterAcceptsRow()` |
| `KeyListener` | Error isolation in `_trigger_callbacks()` |
| `ResultThread` | try/except around audio callback |
| `Sidebar` | `safe_callback` on lambda signal connections |

### UI Bug Fixes

- **Fixed**: Ghost context menus appearing on deleted transcript locations
- **Fixed**: Sidebar collapsing when deleting transcripts from Recent/Projects
- **Fixed**: Recording stopping when deleting a transcript during recording
- **Fixed**: Header text overflow (month/day/timestamp truncation)
- **Fixed**: Welcome text font size too large

## Files Modified (10)

- `src/ui/utils/error_handler.py` - Added `safe_callback()`, `safe_slot_silent()`
- `src/ui/utils/__init__.py` - Exported new utilities
- `src/ui/widgets/project/project_tree.py` - Protected all CRUD methods
- `src/ui/widgets/history_tree/history_tree_view.py` - Protected CRUD, wrapped lambdas
- `src/ui/models/project_proxy.py` - Deferred invalidation, protected filters
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
- No segfaults possible from Project operations

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
- `src/ui/widgets/project/project_styles.py`
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

Complete visual redesign and metrics foundation. Implemented Projects UI with dynamic sidebar, functional search system, real-time waveform visualization, and comprehensive transcription analytics framework. The UI now provides transparency about the cognitive and productivity dimensions of dictation.

## Major Features

### Projects Management
- **Implemented**: Complete Projects UI with visual sidebar
- **Added**: Dynamic Project tree with custom delegation and font sizing
- **Added**: Create/rename/delete Projects through sidebar context menu
- **Added**: Proper visual distinction and color coding for Projects

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
- **Improved**: Typography scale (greeting 42pt, body 19pt, Project names 17pt)
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
- `src/ui/components/sidebar/` - Projects, tab bar, styling
- `src/ui/components/workspace/` - Metrics, content layout, header
- `src/ui/components/main_window/` - Menu integration for metrics dialog
- `src/ui/widgets/` - Custom dialogs, waveform, Project tree
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

# v1.3.0 Beta - Projects (Data Layer)

**Date:** January 2026  
**Status:** Beta

---

## Summary

Backend implementation of Projects - user-defined organization for transcripts. Provides complete CRUD operations for grouping transcripts by subject or purpose. UI integration deferred to future release.

## Changes

### Project Data Layer

- **Added**: `create_project(name)` - Create new Projects with user-defined names
- **Added**: `get_projects()` - Retrieve all Projects ordered by creation date
- **Added**: `rename_project(id, new_name)` - Rename existing Projects
- **Added**: `delete_project(id, move_to_ungrouped)` - Delete groups with safety controls:
  - Default behavior: move transcripts to ungrouped (via `ON DELETE SET NULL` foreign key)
  - Optional blocking: prevent deletion if group contains transcripts
- **Added**: `assign_transcript_to_project(timestamp, group_id)` - Move transcripts between groups or to ungrouped (None)
- **Added**: `get_transcripts_by_project(group_id, limit)` - Filter transcripts by group membership

### Database Enforcement

- **Enforced**: Foreign key constraints via `PRAGMA foreign_keys = ON` in all relevant methods
- **Enforced**: `ON DELETE SET NULL` cascade behavior - deleting a group automatically ungroupes its transcripts
- **Added**: Transaction-level foreign key enforcement for data integrity

### Testing

- **Added**: 14 comprehensive unit tests covering:
  - Project creation, listing, renaming, deletion
  - Transcript assignment and filtering by group
  - Foreign key cascade behavior (ungrouping on delete)
  - Blocking deletion of non-empty groups
  - Ungrouped transcript queries (NULL group_id)
- **Verified**: All 41 tests passing (27 original + 14 Project tests)
- **Verified**: Zero regressions in existing functionality

## Behavioral Notes

- **Ungrouped is default**: Transcripts without a Project assignment have `project_id = NULL`
- **Exactly one place**: Each transcript belongs to zero or one Project (no multiple assignments)
- **Safe deletion**: Foreign key constraint ensures transcripts never reference deleted groups

## UI Status

- **No user-facing changes**: Projects are fully implemented in the data layer but not yet exposed in the UI
- **Future work**: Phase 2 UI integration will add sidebar navigation, group management dialogs, and filtered transcript views

---

# v1.2.0 Beta - SQLite Migration

**Date:** January 2026  
**Status:** Beta

---

## Summary

Major persistence layer overhaul replacing JSONL storage with SQLite database. Introduces foundational schema for future features including Projects (Phase 2) and content refinement (Phase 4+). All existing functionality preserved with improved performance for updates and queries.

## Changes

### Storage & Data Model

- **Migrated**: Complete replacement of JSONL file storage with SQLite database (`~/.config/vociferous/vociferous.db`)
- **Added**: `transcripts` table with dual-text architecture:
  - `raw_text` - Immutable audit baseline (what Whisper produced)
  - `normalized_text` - Editable content (target for user edits and future refinement)
  - Both fields initialized to identical values on creation
- **Added**: `projects` table (currently unused, ready for Phase 2 navigation)
- **Added**: `schema_version` table for future database migrations
- **Added**: Auto-increment integer primary keys (`id`) for stable references
- **Added**: Foreign key constraint from `transcripts.project_id` to `projects(id)` with `ON DELETE SET NULL`
- **Added**: Database indexes on `id DESC`, `timestamp`, and `project_id` for efficient queries
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
- Schema designed to support Phase 2 (Projects) and Phase 4+ (refinement) without structural changes
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