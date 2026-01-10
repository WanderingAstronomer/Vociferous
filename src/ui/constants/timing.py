"""
Timing and animation constants.

Durations for animations, delays for input simulation, and polling intervals.

Usage:
    from ui.constants import Timing
    QTimer.singleShot(Timing.UI_TRANSITION_MS, callback)

Timer Types (from Qt documentation):
    - PreciseTimer: Try to keep accuracy within 1ms (high CPU)
    - CoarseTimer: Try to keep accuracy within 5% of interval (recommended for UI)
    - VeryCoarseTimer: Round to nearest second (for background tasks)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtCore import Qt


class TimerType:
    """Qt timer precision types for different use cases."""

    @property
    def ANIMATION(self):
        """Animation timer type (CoarseTimer for reduced CPU usage)."""
        from PyQt6.QtCore import Qt
        return Qt.TimerType.CoarseTimer

    @property
    def PRECISE(self):
        """Precise timer type (PreciseTimer for exact timing)."""
        from PyQt6.QtCore import Qt
        return Qt.TimerType.PreciseTimer

    @property
    def BACKGROUND(self):
        """Background timer type (VeryCoarseTimer for background tasks)."""
        from PyQt6.QtCore import Qt
        return Qt.TimerType.VeryCoarseTimer


# Singleton instance
TimerType = TimerType()


class AnimationDurations:
    """Animation timing constants in milliseconds."""

    PULSE_CYCLE = 800  # Recording indicator pulse
    UI_TRANSITION = 220  # Sidebar/button animations
    PREVIEW_RESTORE = 1000  # History tree preview reset
    STATUS_MESSAGE = 2500  # Status bar message display
    COPY_FEEDBACK = 1000  # Copy confirmation checkmark
    DEBOUNCE_FILE_RELOAD = 200  # File watcher debounce


class Timing:
    """Application timing constants."""

    # UI animations (milliseconds)
    UI_TRANSITION_MS = 220  # Sidebar/button animations
    PULSE_CYCLE_MS = 800  # Recording indicator pulse cycle
    PREVIEW_RESTORE_MS = 1000  # History tree preview reset
    STATUS_MESSAGE_MS = 2500  # Status bar message display
    COPY_FEEDBACK_MS = 1000  # Copy confirmation checkmark
    DEBOUNCE_FILE_RELOAD_MS = 200  # File watcher debounce

    # Input simulation delays (seconds)
    MODIFIER_KEY_RELEASE = 0.5  # Wait for Alt key release before paste
    KEYSTROKE_DELAY = 0.02  # Inter-character typing delay (20ms)

    # Process management (seconds)
    PROCESS_SHUTDOWN = 0.5  # Dotool process graceful termination
    THREAD_SHUTDOWN_MS = 2000  # ResultThread stop timeout (milliseconds)

    # Audio recording (seconds)
    HOTKEY_SOUND_SKIP = 0.15  # Skip initial audio to avoid key press (150ms)

    # Polling intervals (seconds)
    EVENT_LOOP_POLL = 0.1  # Input listener polling interval (100ms)
    AUDIO_QUEUE_TIMEOUT = 0.1  # Audio queue polling timeout (100ms)

    # UI deferred execution
    DEFERRED_EXEC = 0  # QTimer.singleShot for next event loop


class Opacity:
    """Opacity values for UI animations."""

    FULL = 1.0  # Full visibility
    DIMMED = 0.4  # Dimmed for pulse/breathing effects


# Typing/speaking speed assumptions for metrics
TYPING_SPEED_WPM = 50  # Default typing speed assumption for metrics
SPEAKING_SPEED_WPM = 140  # Default speaking speed used for fallback duration estimates


def defer_call(callback, delay_ms: int = 0) -> None:
    """
    Schedule a callback to execute after current event processing completes.

    This is useful for:
    - Deferring work until after signal/slot chains complete
    - Avoiding re-entrancy issues in event handlers
    - Scheduling cleanup after widget updates

    Args:
        callback: Function to call (no arguments)
        delay_ms: Delay in milliseconds (default 0 = next event loop iteration)

    Example:
        from ui.constants import defer_call
        defer_call(self._finish_initialization)
    """
    from PyQt6.QtCore import QTimer

    QTimer.singleShot(delay_ms, callback)
