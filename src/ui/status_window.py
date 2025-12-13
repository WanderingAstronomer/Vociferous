"""
Status window for recording/transcribing feedback in Vociferous.

This module provides a floating status indicator that appears during
recording and transcription, giving the user visual feedback.

UI/UX Design:
-------------
```
┌─────────────────────────────┐
│      Vociferous        [×]  │  ← Title bar (from BaseWindow)
├─────────────────────────────┤
│   🎤  Recording...          │  ← Status area
└─────────────────────────────┘
```

The window:
- Appears at bottom-center of screen (out of way, but visible)
- Stays on top of other windows (Qt.WindowStaysOnTopHint)
- Hides from taskbar (Qt.Tool flag)
- Shows different icons for recording vs transcribing

PyQt5 Signal/Slot Concepts:
---------------------------

**pyqtSignal**: Defines a signal this class can emit
```python
closeSignal = pyqtSignal()  # No arguments
statusSignal = pyqtSignal(str)  # Takes a string
```

**pyqtSlot**: Decorator marking a method as slot (optional but helps Qt)
```python
@pyqtSlot(str)
def updateStatus(self, status: str): ...
```

**Connection**: Wire signal to slot
```python
self.statusSignal.connect(self.updateStatus)
```

When `statusSignal.emit('recording')` is called (from any thread),
Qt queues a call to updateStatus('recording') on the main thread.

Window Flags Explained:
-----------------------
```python
Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
```

- FramelessWindowHint: No OS decorations (inherited from BaseWindow)
- WindowStaysOnTopHint: Float above normal windows
- Tool: Hide from taskbar/Alt+Tab (utility window, not main app)

These are bit flags, combined with `|` operator.

QPixmap and Scaling:
--------------------
```python
QPixmap(path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
```

- QPixmap: Holds image data optimized for display
- scaled(): Resize with options:
  - KeepAspectRatio: Don't distort
  - SmoothTransformation: High-quality interpolation (vs Fast)

Python 3.12+ Features:
----------------------
- Match/case for status handling
- Pathlib for asset paths
- `|` for combining enum flags (same as bitwise OR)
"""
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QApplication, QLabel, QHBoxLayout

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from ui.base_window import BaseWindow

# Asset paths - resolve relative to project root (two levels up from this file)
ASSETS_DIR = Path(__file__).parent.parent.parent / 'assets'


class StatusWindow(BaseWindow):
    """
    Floating status window showing recording/transcribing state.

    This window provides real-time feedback to the user during dictation.
    It appears when recording starts and disappears when complete.

    Signal Design:
    --------------
    - statusSignal: Emitted BY this class but also RECEIVED by it
      (connected to updateStatus in __init__). This allows external
      code to emit status changes that the window handles.

    - closeSignal: Emitted when window closes. Main app uses this
      to know when user manually closed the window (cancellation).

    This pattern decouples the window from the app - it doesn't
    need to know about VociferousApp, just emit/receive signals.

    Class Attributes:
        statusSignal: Signal accepting status string ('recording', etc.)
        closeSignal: Signal emitted when window is closed

    Instance Attributes:
        icon_label: QLabel displaying microphone/pencil icon
        status_label: QLabel displaying status text
        microphone_pixmap: Pre-loaded recording icon
        pencil_pixmap: Pre-loaded transcribing icon
    """

    statusSignal = pyqtSignal(str)
    closeSignal = pyqtSignal()

    def __init__(self) -> None:
        """Initialize the status window."""
        super().__init__('Vociferous', 280, 100)
        self.initStatusUI()
        self.statusSignal.connect(self.updateStatus)

    def initStatusUI(self) -> None:
        """Initialize the status user interface."""
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)

        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)

        # Load icons using pathlib
        self.microphone_pixmap = QPixmap(str(ASSETS_DIR / 'microphone.png')).scaled(
            32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.pencil_pixmap = QPixmap(str(ASSETS_DIR / 'pencil.png')).scaled(
            32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.icon_label.setPixmap(self.microphone_pixmap)
        self.icon_label.setAlignment(Qt.AlignCenter)

        self.status_label = QLabel('Recording...')
        self.status_label.setFont(QFont('Segoe UI', 12))

        status_layout.addStretch(1)
        status_layout.addWidget(self.icon_label)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch(1)

        self.main_layout.addLayout(status_layout)

    def show(self) -> None:
        """Position the window at bottom center of screen and show."""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()

        x = (screen_geometry.width() - self.width()) // 2
        y = screen_geometry.height() - self.height() - 120

        self.move(x, y)
        super().show()

    def closeEvent(self, event) -> None:
        """Emit close signal when window is closed."""
        self.closeSignal.emit()
        super().closeEvent(event)

    @pyqtSlot(str)
    def updateStatus(self, status: str) -> None:
        """
        Update the window's display based on current status.

        This slot receives status updates from ResultThread (via signal)
        and updates the UI accordingly.

        State Machine:
        --------------
        ```
        [hidden] ──recording──▶ [visible, mic icon]
                                      │
                             transcribing
                                      ▼
                                [visible, pencil icon]
                                      │
                          idle/error/cancel
                                      ▼
                                  [hidden]
        ```

        Match/Case for State Handling:
        ------------------------------
        ```python
        match status:
            case 'recording':    show window, mic icon
            case 'transcribing': change to pencil icon
            case 'idle' | 'error' | 'cancel':  hide window
        ```

        The `|` in the last case matches ANY of those values.
        This is pattern matching union, not bitwise OR.

        Why @pyqtSlot Decorator?
        ------------------------
        Optional but provides benefits:
        - Slightly faster signal dispatch
        - Better error messages if signature mismatch
        - Documents intent (this is meant to be a slot)

        Args:
            status: Current status ('recording', 'transcribing', 'idle', etc.)
        """
        match status:
            case 'recording':
                self.icon_label.setPixmap(self.microphone_pixmap)
                self.status_label.setText('Recording...')
                self.show()
            case 'transcribing':
                self.icon_label.setPixmap(self.pencil_pixmap)
                self.status_label.setText('Transcribing...')
            case 'idle' | 'error' | 'cancel':
                self.close()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    status_window = StatusWindow()
    status_window.show()

    # Simulate status updates for testing
    QTimer.singleShot(3000, lambda: status_window.statusSignal.emit('transcribing'))
    QTimer.singleShot(6000, lambda: status_window.statusSignal.emit('idle'))

    sys.exit(app.exec_())

    sys.exit(app.exec_())
