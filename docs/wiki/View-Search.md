# View: Search

The **Search View** provides a table-based interface for deep exploration of the transcript database. Unlike the chronologically oriented History View, the Search View is optimized for text retrieval and bulk visualization.

<img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/search_and_manage_view.png" alt="Search View" width="800" />

## Component Hierarchy

The view is structured vertically:

1.  **Filter Bar**: A top-level input field (`QLineEdit`) for instantaneous text filtering.
2.  **Results Table**: A `QTableView` displaying filtered results.
    *   **Proxy Model**: Uses `SearchProxyModel` (filtering logic) over the `TranscriptionTableModel`.

---

## Capabilities & Interaction

### Filtering Logic
*   **Scope**: Searches **ALL** columns (Date, Duration, Text).
*   **Sensitivity**: Case-insensitive substring matching.
*   **Behavior**: Real-time filtering as you type.

### Table Layout
*   The text column uses a custom `SearchTextDelegate` to wrap long text and limit row height to approximately **6 lines**.
*   This prevents a single massive transcript from dominating the view while offering enough context to identify the content.

### Actions
*   **Copy**: `Ctrl+C` (or Action Dock button) copies the selected row's raw text.
*   **ContextMenu**: Right-clicking a row offers Copy, Edit, Delete, and Refine actions.
*   **Selection**: Supports Extended Selection (Shift/Ctrl+Click) for future bulk actions (though `delete_requested` currently handles lists).

## Data Integration
Like other views, the Search View subscribes to `DatabaseSignalBridge` to remain perfectly consistent with the underlying database state.
