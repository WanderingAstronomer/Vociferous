"""
Components Package.

High-level UI components that compose widgets into functional areas.

Components:
    MainWindow: Primary application window (sidebar, workspace, metrics strip)
    SidebarWidget: History sidebar with transcript list
    MainWorkspace: Central workspace area (header, controls, content)
    TitleBar: Custom window title bar
    DialogTitleBar: Title bar for dialogs
    SettingsDialog: Application settings dialog
"""

# NOTE: No eager imports! Components import Qt and widgets at module level.
# Import components directly from their modules when needed:
#   from ui.components.main_window import MainWindow
#   from ui.components.settings import SettingsDialog
# etc.
