"""
Vociferous - Simple Speech-to-Text Dictation Application.

This is the main orchestration module that ties together all components:
key listening, audio recording, transcription, and text injection.

Application Architecture:
-------------------------
```
┌─────────────────────────────────────────────────────────────────┐
│                      VociferousApp (QObject)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    callback    ┌─────────────────────┐        │
│  │ KeyListener  │ ──────────────▶│ on_activation()     │        │
│  │ (evdev/      │                │ on_deactivation()   │        │
│  │  pynput)     │                └──────────┬──────────┘        │
│  └──────────────┘                           │                   │
│                                             ▼                   │
│                              ┌──────────────────────────┐       │
│                              │ ResultThread (QThread)   │       │
│                              │ • Record audio           │       │
│                              │ • Run transcription      │       │
│                              └──────────┬───────────────┘       │
│                                         │                       │
│                    Qt Signals           │                       │
│         ┌───────────────────────────────┼───────────────┐       │
│         │                               │               │       │
│         ▼                               ▼               ▼       │
│  ┌──────────────┐              ┌──────────────┐ ┌──────────────┐│
│  │StatusWindow  │              │InputSimulator│ │  Tray Icon   ││
│  │(UI feedback) │              │(text inject) │ │  (status)    ││
│  └──────────────┘              └──────────────┘ └──────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

PyQt5 Concepts Demonstrated:
----------------------------

**1. QApplication and Event Loop**
The app runs an event loop (`app.exec_()`) that processes UI events,
timers, and signal/slot invocations. Everything is event-driven.

**2. Signal/Slot Pattern**
Qt's implementation of the Observer pattern. Signals are emitted by
objects, slots are methods that receive them. Key benefits:
- Type-safe (argument types are checked)
- Thread-safe (cross-thread signals are queued automatically)
- Loose coupling (emitter doesn't know about receivers)

Example from this module:
```python
self.result_thread.resultSignal.connect(self.on_transcription_complete)
#                  ↑ signal                    ↑ slot
```

**3. QThread for Background Work**
ResultThread runs audio recording and transcription off the main thread.
This keeps the UI responsive. Signals safely cross the thread boundary.

**4. System Tray Integration**
QSystemTrayIcon provides the tray icon and right-click menu. Combined
with `setQuitOnLastWindowClosed(False)`, the app runs headlessly.

**5. Resource Management**
`deleteLater()` schedules object deletion on the event loop, preventing
crashes from deleting objects that still have pending signals.

Thread Connection Management:
-----------------------------
This module tracks signal connections in `_thread_connections` list.
This allows proper cleanup when threads finish or the app exits:

```python
for signal, slot in self._thread_connections:
    signal.connect(slot)  # Connect
    # ... later ...
    signal.disconnect(slot)  # Clean disconnect
```

Without explicit disconnection, you can get:
- Memory leaks (slots keep objects alive)
- Crashes (signals delivered to deleted objects)
- Unexpected behavior (old handlers still firing)

Recording Modes:
----------------
- `press_to_toggle`: Press once to start, press again to stop
- `hold_to_record`: Hold key to record, release to stop

The mode affects which callback (on_activation vs on_deactivation)
triggers the stop_recording action.

Python 3.12+ Features:
----------------------
- Match/case for status text selection
- `list[tuple]` generic type hints without imports
- `Path` objects for asset paths
"""
import logging
import sys
from pathlib import Path

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction

from key_listener import KeyListener
from result_thread import ResultThread
from ui.status_window import StatusWindow
from transcription import create_local_model
from input_simulation import InputSimulator
from utils import ConfigManager

logger = logging.getLogger(__name__)

# Asset paths - resolve relative to project root (one level up from src/)
ASSETS_DIR = Path(__file__).parent.parent / 'assets'
LOGO_PATH = ASSETS_DIR / 'ww-logo.png'


class VociferousApp(QObject):
    """
    Main application orchestrator for Vociferous speech-to-text.

    This class follows the Mediator pattern - it coordinates communication
    between components (KeyListener, ResultThread, StatusWindow, etc.)
    without them knowing about each other.

    Lifecycle:
    ----------
    1. __init__: Create QApplication, initialize ConfigManager
    2. initialize_components: Load model, create UI, set up listeners
    3. run: Enter Qt event loop (blocking)
    4. cleanup: Stop threads, release resources
    5. exit_app: Quit event loop

    Why inherit from QObject?
    -------------------------
    QObject provides:
    - Signal/slot mechanism (not used here but available)
    - Parent-child ownership (automatic cleanup)
    - deleteLater() for safe deferred deletion
    - Thread affinity (objects belong to threads)

    Even though we don't define signals here, inheriting QObject makes
    this class a proper Qt citizen that can participate in the ecosystem.

    Attributes:
        app: QApplication instance (singleton, one per process)
        key_listener: Hotkey detection (evdev/pynput backend)
        local_model: Loaded Whisper model (kept in memory for fast inference)
        result_thread: Current recording/transcription thread (or None)
        status_window: UI showing recording/transcribing state
        input_simulator: Text injection (pynput/ydotool/etc.)
        tray_icon: System tray presence
        _thread_connections: Tracked signal connections for cleanup
    """

    def __init__(self) -> None:
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Vociferous")
        self.app.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.app.setQuitOnLastWindowClosed(False)  # Keep running in tray

        # Initialize config
        ConfigManager.initialize()

        # Track active signal connections for cleanup
        self._thread_connections: list[tuple] = []

        # Initialize components
        self.initialize_components()

    def initialize_components(self) -> None:
        """
        Initialize all application components in dependency order.

        Initialization order matters:
        1. InputSimulator - no dependencies
        2. KeyListener - needs config loaded (done in __init__)
        3. Whisper model - slow, loaded early to avoid first-use delay
        4. StatusWindow - needs Qt app running
        5. Tray icon - needs Qt app and logo asset
        6. Start listening - only after everything else is ready

        Why load model eagerly?
        -----------------------
        Model loading takes 2-10 seconds depending on size and device.
        Loading it at startup means the first dictation is instant.
        The tradeoff is slower startup, but better UX during use.
        """
        ConfigManager.console_print("Initializing Vociferous...")

        # Input simulator for text injection
        self.input_simulator = InputSimulator()

        # Key listener for hotkey detection
        self.key_listener = KeyListener()
        self.key_listener.add_callback("on_activate", self.on_activation)
        self.key_listener.add_callback("on_deactivate", self.on_deactivation)

        # Load whisper model
        ConfigManager.console_print("Loading Whisper model (this may take a moment)...")
        self.local_model = create_local_model()

        # Result thread (for recording/transcription)
        self.result_thread = None

        # Status window (shows recording/transcribing state)
        self.status_window = StatusWindow()

        # System tray
        self.create_tray_icon()

        # Start listening for hotkey
        self.key_listener.start()

        activation_key = ConfigManager.get_config_value(
            'recording_options', 'activation_key'
        )
        ConfigManager.console_print(f"Ready! Press '{activation_key}' to start.")

    def create_tray_icon(self) -> None:
        """
        Create the system tray icon with context menu.

        System Tray Pattern:
        --------------------
        For "headless" apps that run in background:
        1. setQuitOnLastWindowClosed(False) - don't exit when windows close
        2. Create QSystemTrayIcon with icon
        3. Attach QMenu for right-click actions
        4. show() to make visible

        The tray icon serves as:
        - Visual indicator that the app is running
        - Status display (tooltip updates with state)
        - Exit point (right-click → Exit)
        """
        self.tray_icon = QSystemTrayIcon(
            QIcon(str(LOGO_PATH)),
            self.app
        )

        tray_menu = QMenu()

        # Status indicator (non-clickable)
        status_action = QAction('Vociferous - Ready', self.app)
        status_action.setEnabled(False)
        tray_menu.addAction(status_action)
        self.status_action = status_action

        tray_menu.addSeparator()

        # Exit action
        exit_action = QAction('Exit', self.app)
        exit_action.triggered.connect(self.exit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("Vociferous - Speech to Text")
        self.tray_icon.show()

    def on_activation(self):
        """Called when activation key is pressed."""
        recording_mode = ConfigManager.get_config_value(
            'recording_options', 'recording_mode'
        )

        if self.result_thread and self.result_thread.isRunning():
            # Already recording - stop it
            if recording_mode == 'press_to_toggle':
                self.result_thread.stop_recording()
            return

        # Start new recording
        self.start_result_thread()

    def on_deactivation(self):
        """Called when activation key is released (for hold_to_record mode)."""
        recording_mode = ConfigManager.get_config_value(
            'recording_options', 'recording_mode'
        )

        if recording_mode == 'hold_to_record':
            if self.result_thread and self.result_thread.isRunning():
                self.result_thread.stop_recording()

    def start_result_thread(self):
        """
        Start a new recording and transcription thread.

        Thread Lifecycle:
        -----------------
        1. Check if thread already running (prevent double-start)
        2. Disconnect previous signals (prevent dangling connections)
        3. Create new ResultThread with loaded model
        4. Connect signals to UI and processing slots
        5. Connect finished signal for auto-cleanup
        6. Start the thread

        Signal Connection Pattern:
        --------------------------
        We store connections in `_thread_connections` list:
        ```python
        self._thread_connections = [
            (signal, slot),
            (signal, slot),
            ...
        ]
        ```

        This pattern allows:
        - Bulk connect/disconnect operations
        - Proper cleanup when thread finishes
        - Prevention of "zombie" connections

        The `finished.connect(self._on_thread_finished)` sets up auto-cleanup:
        when the thread completes, we disconnect all signals and schedule
        the thread object for deletion.
        """
        if self.result_thread and self.result_thread.isRunning():
            return

        # Clean up any previous thread connections
        self._disconnect_thread_signals()

        self.result_thread = ResultThread(self.local_model)

        # Store connections for later cleanup (allows proper disconnection)
        self._thread_connections = [
            (self.result_thread.statusSignal, self.status_window.updateStatus),
            (self.result_thread.statusSignal, self.update_tray_status),
            (self.status_window.closeSignal, self.stop_result_thread),
            (self.result_thread.resultSignal, self.on_transcription_complete),
        ]

        # Connect all signals
        for signal, slot in self._thread_connections:
            signal.connect(slot)

        # Auto-cleanup: when thread finishes, disconnect signals and schedule deletion
        self.result_thread.finished.connect(self._on_thread_finished)
        self.result_thread.start()

    def _disconnect_thread_signals(self) -> None:
        """Safely disconnect all tracked thread signal connections."""
        for signal, slot in self._thread_connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                # Already disconnected or object deleted
                pass
        self._thread_connections.clear()

    def _on_thread_finished(self) -> None:
        """Handle thread completion: cleanup signals and schedule deletion."""
        self._disconnect_thread_signals()
        if self.result_thread:
            self.result_thread.deleteLater()

    def stop_result_thread(self) -> None:
        """Stop the recording/transcription thread."""
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop()

    def update_tray_status(self, status: str) -> None:
        """
        Update tray icon tooltip based on current status.

        Uses match/case for clean status-to-text mapping:
        ```python
        match status:
            case 'recording':    text = '...Recording...'
            case 'transcribing': text = '...Transcribing...'
            case _:              text = '...Ready'
        ```

        The wildcard `_` case handles any unexpected status values,
        providing a safe default rather than raising an error.

        Args:
            status: Status string ('recording', 'transcribing', 'error', etc.)
        """
        match status:
            case 'recording':
                text = 'Vociferous - Recording...'
            case 'transcribing':
                text = 'Vociferous - Transcribing...'
            case 'error':
                text = 'Vociferous - Error'
            case _:
                text = 'Vociferous - Ready'
        self.status_action.setText(text)

    def on_transcription_complete(self, result: str) -> None:
        """
        Handle completed transcription - inject text into active window.

        This is the final step in the dictation pipeline:
        Audio → Recording → Transcription → **Text Injection**

        The InputSimulator handles the complexity of text injection across
        different display servers (X11, Wayland) and input methods.

        Args:
            result: Transcribed text to inject (may be empty string)
        """
        if result:
            self.input_simulator.typewrite(result)

    def cleanup(self) -> None:
        """Clean up resources."""
        # Stop and clean up result thread
        if self.result_thread and self.result_thread.isRunning():
            self.result_thread.stop()
            self.result_thread.wait(2000)  # Wait up to 2 seconds for graceful stop
        self._disconnect_thread_signals()

        if self.key_listener:
            self.key_listener.stop()
        if self.input_simulator:
            self.input_simulator.cleanup()

    def exit_app(self) -> None:
        """Exit the application."""
        self.cleanup()
        QApplication.quit()

    def run(self) -> int:
        """Run the application."""
        return self.app.exec_()


if __name__ == '__main__':
    app = VociferousApp()
    sys.exit(app.run())
