"""
Enumerations and state constants.

Application state definitions for workspace and other stateful components.
"""

from enum import Enum


class WorkspaceState(Enum):
    """Main workspace states (mutually exclusive)."""

    IDLE = "idle"  # No transcript selected, not recording
    RECORDING = "recording"  # Actively recording audio
    VIEWING = "viewing"  # Transcript selected, read-only
    EDITING = "editing"  # Explicit edit mode
