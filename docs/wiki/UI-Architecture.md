# UI Architecture

The Vociferous UI is built with **PyQt6** using a strictly component-based architecture. It avoids monolithic "God Classes" by splitting functionality into independent, reusable widgets and composed components.

## Directory Structure

`src/ui/` is the root of the UI subsystem.

```text
src/ui/
├── components/         # High-level "page" or "region" controllers
│   ├── main_window/    # The application shell and layout
│   ├── icon_rail/      # The left-hand navigation rail
│   ├── workspace/      # The right-hand active content area
│   ├── view_host/      # View routing and management (QStackedWidget)
│   ├── action_dock/    # Context-sensitive action buttons
│   ├── title_bar/      # Custom frameless window controls
│   └── settings/       # Settings dialogs (legacy)
├── views/              # Full-screen surfaces (main content areas)
│   ├── transcribe_view.py  # Recording interface
│   ├── history_view.py     # Browse transcriptions
│   ├── projects_view.py    # Project organization
│   ├── refinement_view.py  # AI editing surface
│   ├── settings_view.py    # Configuration management
│   └── user_view.py        # Metrics and information
├── widgets/            # Low-level reusable UI elements
│   ├── project/    # Tree view for organizing transcripts
│   ├── history_tree/   # List view of transcripts
│   ├── metrics_strip/  # Real-time dashboard (WPM, duration)
│   ├── transcript_item/# Rich text rendering for transcript cards
│   └── ...
├── styles/             # Theming engine
├── constants/          # Design system (colors, spacing, typography)
└── models/             # Qt Abstract Models (data binding)
```

## Atomic Design Philosophy

We generally follow atomic design principles:

1.  **Tokens** (`ui/constants/`): Raw values for Spacing, Colors, Timing.
2.  **Widgets** (`ui/widgets/`): Simple, single-purpose elements (e.g., `StyledButton`, `WaveformVisualizer`).
3.  **Components** (`ui/components/`): Complex compositions of widgets (e.g., `IconRail`, `ViewHost`, `ActionDock`).
4.  **Views** (`ui/views/`): Full-screen surfaces for major features (Transcribe, History, Settings, etc.).
5.  **Main Window**: The orchestrator that wires components together.

## Theming System

Vociferous does **not** use QSS files scattered throughout the repo. Instead, it uses a Python-based styling system that generates a single optimized QSS string at runtime.

*   **Source**: `src/ui/styles/unified_stylesheet.py`
*   **Tokens**: `src/ui/styles/theme.py` (references constants)
*   **Registry**: `src/ui/styles/stylesheet_registry.py` allows widgets to register their own CSS chunks.

### Adding Styles

Do not call `widget.setStyleSheet()` directly. Instead:
1. Define a style function in the widget's `_styles.py` file.
2. Register it in `unified_stylesheet.py` or have the widget return it.
3. The app compiles it into one global stylesheet on launch.

## Key Components

### 1. MainWindow (`ui/components/main_window/`)
The shell. It creates the custom title bar, the Icon Rail, the ViewHost, and manages global state. It handles:
*   Window moving/resizing (frameless)
*   System tray minimization logic
*   Global state orchestration
*   Intent routing from views to backend systems

### 2. IconRail (`ui/components/icon_rail/`)
The navigation hub—a vertical rail of icons on the left side.
*   **Navigation Icons**: Transcribe, History, Projects, Refinement (conditionally shown)
*   **Bottom Cluster**: User, Settings icons with visual separator
*   **View Gating**: Checks `ConfigManager` to conditionally show/hide views (e.g., Refinement requires `refinement.enabled`)
*   **Intent Emission**: Emits `NavigateIntent` when icons are clicked

### 3. ViewHost (`ui/components/view_host/`)
The view router—manages which view is currently visible using `QStackedWidget`.
*   **Views**: Transcribe, History, Projects, Refinement, Settings, User
*   **Routing**: `switch_to_view()` method activates views by name
*   **Lifecycle**: Calls `refresh()` on views when activated
*   **Signals**: Emits `viewChanged` to notify observers (ActionDock) of navigation

### 4. Views (`ui/views/`)
Full-screen surfaces representing major features:

*   **TranscribeView**: Main recording interface with waveform and controls
*   **HistoryView**: Browse all past transcriptions
*   **ProjectsView**: Organize transcripts by topic
*   **RefinementView**: AI-powered editing surface
*   **SettingsView**: Configuration management (replaces old SettingsDialog)
    - Form-based settings with inline validation
    - Hotkey configuration via `HotkeyWidget`
    - Export/Clear history controls
    - Restart/Exit buttons
*   **UserView**: User information and metrics
    - Lifetime metrics (total transcriptions, words, time saved)
    - About section (version, license)
    - Help section (keyboard shortcuts)

### 5. ActionDock (`ui/components/action_dock/`)
Context-sensitive action buttons that adapt to current view and state:
*   **Dynamic Grid**: Shows different buttons based on view (e.g., "Record" on Transcribe, "Edit/Delete" on History)
*   **State Awareness**: Adapts to recording/transcribing/idle states
*   **Intent Emission**: All actions emit intents that propagate to MainWindow

## Data Binding (Models)

We use Qt's Model/View architecture for lists of data.

*   **`TranscriptionModel`**: Wraps the list of history entries.
*   **`ProjectProxy`**: A `QSortFilterProxyModel` that filters the flat history list based on the selected Project in the sidebar.

## Custom Painting

Performance-critical widgets use custom `paintEvent` handlers instead of composite widgets:

*   **`WaveformVisualizer`**: Draws audio amplitudes using `QPainter` for high frame rates (60fps).
*   **`TranscriptItem`**: The history list items are drawn manually by a Delegate to support complex layouts (badges, timestamps, text truncation) without the overhead of creating hundreds of widgets.

## Interaction Layer (Intents)

To decouple user intent from execution logic, we use the **Intent Pattern** (`src/ui/interaction/`).

*   **Intents** are immutable dataclasses (e.g., `ViewTranscriptIntent`, `SearchIntent`).
*   **Producers**: Low-level widgets (buttons, list items) create intents.
*   **Consumers**: High-level controllers (`MainWindow`, `MainWorkspace`) consume intents and execute logic.

This prevents "spaghetti code" where a button deeper in the hierarchy tries to directly manipulate a sibling widget.

## Signal Flow

Communication follows a strict hierarchy to prevent coupling:

1.  **Child Widget** emits signal (e.g., `buttonClicked`) carrying an `Intent` or simple state.
2.  **View** catches signal, validates context, and emits a semantic intent (e.g., `BeginRecordingIntent`).
3.  **MainWindow** connects view signals to backend systems (HistoryManager, TranscriptionEngine, etc.).

**Critical Rule**: Views do not communicate directly. They emit intents upward to MainWindow, which coordinates all cross-view state changes.

## Navigation Model

As of v2.6.0, Vociferous uses an **Icon Rail navigation model**:

*   **No Menu Bar**: Traditional file/edit/view menus have been removed.
*   **Icon-Based Navigation**: All major features accessible via IconRail icons.
*   **Settings View**: Configuration managed through dedicated full-screen Settings view (not a dialog).
*   **User View**: Metrics, about info, and help accessed via User icon (bottom of rail).
*   **Conditional Views**: Some views (e.g., Refinement) only appear if enabled in config.

### Navigation Flow

```
User clicks Icon → IconRail emits NavigateIntent → MainWindow receives intent
→ MainWindow calls ViewHost.switch_to_view() → ViewHost shows target view
→ ViewHost emits viewChanged → ActionDock updates button grid
```

This ensures:
- **Single Source of Truth**: ViewHost tracks active view
- **Decoupling**: Views don't know about each other
- **Extensibility**: New views just need registration in ViewHost
