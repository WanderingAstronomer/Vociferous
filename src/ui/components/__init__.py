"""
Components Package.

High-level UI components that compose widgets into functional areas.

Organization:
    main_window/: Primary application window and its sub-components
        - MainWindow: Application shell orchestrator
        - ActionDock: Context-sensitive action buttons
        - IconRail: Navigation rail with view icons
        - SystemTrayManager: System tray integration
        - ViewHost: View routing and switching
        - IntentFeedback: Intent feedback handler
    title_bar/: Custom window title bars
        - TitleBar: Main window title bar
        - DialogTitleBar: Dialog title bar
    workspace/: Right-side workspace area
        - MainWorkspace: Workspace container
        - WorkspaceHeader: Workspace header
        - WorkspaceContent: Content display area
        - TranscriptMetrics: Metrics display
    view_utilities/: Shared view helper components
        - ContentPanel: Detail display panel
        - HistoryList: History list wrapper
"""

# NOTE: No eager imports! Components import Qt and widgets at module level.
# Import components directly from their modules when needed:
#   from src.ui.components.main_window import MainWindow
#   from src.ui.components.shared import ContentPanel
# etc.
