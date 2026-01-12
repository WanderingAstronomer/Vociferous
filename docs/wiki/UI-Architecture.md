# UI Architecture

The Vociferous UI is built with **PyQt6** using a strictly component-based architecture. It avoids monolithic "God Classes" by splitting functionality into independent, reusable widgets and composed components.

## Directory Structure

`src/ui/` is the root of the UI subsystem.

```text
src/ui/
├── components/         # High-level "page" or "region" controllers
│   ├── main_window/    # The application shell and layout
│   ├── sidebar/        # The left-hand navigation and properties panel
│   ├── workspace/      # The right-hand active content area
│   ├── title_bar/      # Custom frameless window controls
│   └── settings/       # Settings dialogs
├── widgets/            # Low-level reusable UI elements
│   ├── focus_group/    # Tree view for organizing transcripts
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
3.  **Components** (`ui/components/`): Complex compositions of widgets (e.g., `Sidebar`, `Workspace`).
4.  **Main Window**: The orchestrator that wires components together.

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
The shell. It creates the custom title bar, the sidebar, and the workspace. It handles:
*   Window moving/resizing (frameless)
*   System tray minimization logic
*   Global state orchestration

### 2. Sidebar (`ui/components/sidebar/`)
The navigation hub.
*   **Focus Groups**: Hierarchical organization of transcripts.
*   **Search**: Full-text filtering.
*   **History**: A `QTreeView` displaying transcripts, delegating rendering to `HistoryTreeDelegate`.

### 3. Workspace (`ui/components/workspace/`)
The "Work Bench".
*   **Header**: Shows current Focus Group or active transcript title.
*   **Content**: The main text editor / viewer area.
*   **Controls**: The "Record" button and Waveform visualization.
*   **Metrics**: The statistics bar at the bottom.

## Data Binding (Models)

We use Qt's Model/View architecture for lists of data.

*   **`TranscriptionModel`**: Wraps the list of history entries.
*   **`FocusGroupProxy`**: A `QSortFilterProxyModel` that filters the flat history list based on the selected Focus Group in the sidebar.

## Custom Painting

Performance-critical widgets use custom `paintEvent` handlers instead of composite widgets:

*   **`WaveformVisualizer`**: Draws audio amplitudes using `QPainter` for high frame rates (60fps).
*   **`TranscriptItem`**: The history list items are drawn manually by a Delegate to support complex layouts (badges, timestamps, text truncation) without the overhead of creating hundreds of widgets.

## Signal Flow

Communication follows the hierarchy:

1.  **Child Widget** emits signal (e.g., `recordClicked`)
2.  **Component** catches signal, maybe processes it, and re-emits a semantic signal (e.g., `startRecordingRequested`).
3.  **MainWindow** connects component signals to `Main` controller or other components.

**Rule**: Siblings (Sidebar vs Workspace) do not talk directly. They communicate via the `MainWindow` or shared Data Models.
