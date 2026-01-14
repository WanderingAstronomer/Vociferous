"""
Widget layer - Reusable UI components for Vociferous.

Each widget is in its own subpackage with co-located styles.

Available widgets:
- collapsible_section: Expandable/collapsible sections
- content_panel: Custom painted content panels
- dialogs: Various dialog types (confirmation, input, message, create group)
- project: Project tree and container widgets
- history_tree: Day-grouped history tree view
- hotkey_widget: Hotkey recording widget
- metrics_strip: Metrics display strip
- styled_button: Custom styled buttons
- transcript_item: Tree item factories for transcripts
- waveform_visualizer: Audio waveform visualization
"""

# NOTE: No eager imports! All widgets import Qt at module level.
# Import widgets directly from their subpackages when needed:
#   from ui.widgets.collapsible_section import CollapsibleSection
#   from ui.widgets.dialogs import ConfirmationDialog
# etc.
