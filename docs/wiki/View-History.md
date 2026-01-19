# View: History

The **History View** provides a master-detail interface for navigating active and archived transcripts. It is designed for quick browsing and detailed review without leaving the main window context.

<img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/history_view.png" alt="History View" width="800" />

## Component Hierarchy

The view employs a split-pane layout:

1.  **History Panel (Left)**: a `HistoryList` widget displaying a scrollable list of past sessions, sorted by date.
    *   Displays timestamp, duration, and a snippet of the text.
    *   Grouped by relative dates (Today, Yesterday, etc.) - *Implementation dependent*.
2.  **Content Panel (Right)**: A read-only detail view (`ContentPanel`) showing the full transcript of the selected item.

---

## Capabilities & Interaction

This view focuses on **Consumption and Management**.

### Selection
*   **Single Selection**: Clicking an item in the left list populates the right panel instantly.
*   **Selection State**: The view broadcasts the selected ID to the global `ActionDock` to enable relevant buttons.

### Actions
When an item is selected, the following actions become available in the global toolbar:

*   `Copy`: Copies the full text of the selected transcript to the clipboard.
*   `Edit`: Navigates to the **Edit View** (or switches workspace to Edit mode) for the selected transcript.
*   `Delete`: Removes the transcript from the database.
*   `Refine`: Sends the transcript to the Refinement View for post-processing.

## Data Integration
The view connects directly to the `HistoryManager` and listens for `DatabaseSignalBridge` events. Updates from other views (e.g., a new recording in Transcribe View) automatically appear in the list without manual refresh.
