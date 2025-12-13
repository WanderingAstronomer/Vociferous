"""
Base window class for Vociferous UI components.

This module provides a custom frameless window with rounded corners,
used as the base for status displays and other floating UI elements.

PyQt5 Custom Window Concepts:
-----------------------------

**1. Frameless Windows**
Standard windows have OS-provided title bars and borders. By setting
`Qt.FramelessWindowHint`, we remove those and take full control of
the window's appearance. The tradeoff: we must implement dragging,
close buttons, and borders ourselves.

**2. Translucent Background**
```python
self.setAttribute(Qt.WA_TranslucentBackground, True)
```

This makes the window background transparent, allowing our custom
`paintEvent` to draw any shape we want (rounded rectangle here).
Without this, you'd see a rectangular background behind the rounded corners.

**3. Custom Painting**
Qt's painting system uses QPainter for all drawing:
```python
def paintEvent(self, event):
    painter = QPainter(self)
    painter.drawPath(path)  # Draw our rounded rect
```

The paintEvent is called automatically when Qt decides the window
needs redrawing (resize, expose, update() called, etc.).

**4. Mouse Event Handling for Drag**
Frameless windows can't be dragged by default. We implement it:
- `mousePressEvent`: Record starting position
- `mouseMoveEvent`: Calculate delta, move window
- `mouseReleaseEvent`: Stop tracking

This is the classic \"drag\" pattern in GUI programming.

Window Hierarchy:
-----------------
```
QMainWindow (BaseWindow)
    └── QWidget (main_widget)
            └── QVBoxLayout (main_layout)
                    ├── QWidget (title_bar)
                    │       └── QHBoxLayout
                    │               ├── Spacer
                    │               ├── QLabel (\"Vociferous\")
                    │               └── QPushButton (\"×\")
                    └── [Content added by subclasses]
```

QPainterPath for Shapes:
------------------------
QPainterPath is a \"vector path\" that can describe any shape:
- moveTo, lineTo: Straight lines
- cubicTo: Bezier curves
- addRoundedRect: Rounded rectangle (used here)

We fill the path with a semi-transparent brush for the frosted-glass look.

Why QMainWindow?
----------------
QMainWindow provides structure (central widget, dock areas, menu bar).
Even though we don't use most features, it gives us `setCentralWidget()`
for easy content management. QWidget would also work for simpler cases.

Python 3.14+ Features:
----------------------
- Type hints with `| None` union syntax (in other files)
- Method signatures with return type annotations
"""
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QGuiApplication, QPainter, QPainterPath
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class BaseWindow(QMainWindow):
    """
    Frameless, draggable window with rounded corners and translucent background.

    This serves as the base class for Vociferous UI windows. It provides:
    - Custom-painted rounded rectangle background
    - Title bar with close button
    - Drag-to-move from anywhere on the window
    - Auto-centering on primary screen

    Design Rationale:
    -----------------
    Traditional OS window decorations don't fit the "floating overlay" aesthetic
    we want for status indicators. By going frameless, we get:
    - Visual consistency across Linux DEs/WMs
    - Modern, minimal appearance
    - Full control over look and feel

    The tradeoff is complexity - we implement our own close button and drag.

    Instance Attributes:
        is_dragging: Currently being dragged by user?
        start_position: Mouse position at drag start (for delta calculation)
        main_widget: Central container widget
        main_layout: Vertical layout for content
    """
    def __init__(self, title: str, width: int, height: int) -> None:
        """Initialize the base window."""
        super().__init__()
        self.is_dragging: bool = False
        self.start_position = None
        self.initUI(title, width, height)
        self.setWindowPosition()

    def initUI(self, title: str, width: int, height: int) -> None:
        """
        Initialize the user interface components.

        Window Setup Sequence:
        ----------------------
        1. setWindowTitle: Shows in taskbar/Alt+Tab (even if frameless)
        2. setWindowFlags: Remove frame, title bar, borders
        3. setAttribute: Enable translucent background for custom painting
        4. setFixedSize: Prevent user resizing

        Layout Structure:
        -----------------
        QVBoxLayout stacks widgets vertically:
        - Title bar at top (with close button)
        - Subclass content below

        The spacer widgets in the title bar layout center the title:
        [Spacer:1] [Title:3] [Button:1]

        The numbers are stretch factors - title gets 3x the space.

        StyleSheet (CSS-like):
        ----------------------
        Qt supports a subset of CSS for widget styling:
        ```css
        QPushButton:hover { color: #000000; }
        ```
        Pseudo-states like :hover work similarly to CSS.
        """
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(width, height)

        self.main_widget = QWidget(self)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # Create a widget for the title bar
        title_bar = QWidget()
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)

        # Add the title label
        title_label = QLabel('Vociferous')
        title_label.setFont(QFont('Segoe UI', 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #404040;")

        # Create a widget for the close button
        close_button_widget = QWidget()
        close_button_layout = QHBoxLayout(close_button_widget)
        close_button_layout.setContentsMargins(0, 0, 0, 0)

        close_button = QPushButton('×')
        close_button.setFixedSize(25, 25)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #404040;
            }
            QPushButton:hover {
                color: #000000;
            }
        """)
        close_button.clicked.connect(self.handleCloseButton)

        close_button_layout.addWidget(close_button, alignment=Qt.AlignRight)

        # Add widgets to the title bar layout
        title_bar_layout.addWidget(QWidget(), 1)  # Left spacer
        title_bar_layout.addWidget(title_label, 3)  # Title (with more width)
        title_bar_layout.addWidget(close_button_widget, 1)  # Close button

        self.main_layout.addWidget(title_bar)
        self.setCentralWidget(self.main_widget)

    def setWindowPosition(self) -> None:
        """Center the window on the primary screen."""
        center_point = QGuiApplication.primaryScreen().availableGeometry().center()
        frame_geometry = self.frameGeometry()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def handleCloseButton(self) -> None:
        """Close the window."""
        self.close()

    def mousePressEvent(self, event) -> None:
        """Allow window dragging from anywhere."""
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        """Move the window when dragging."""
        if Qt.LeftButton and self.is_dragging:
            self.move(event.globalPos() - self.start_position)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        """Stop dragging the window."""
        self.is_dragging = False

    def paintEvent(self, event) -> None:
        """
        Custom paint handler for rounded, semi-transparent background.

        Qt Painting Architecture:
        -------------------------
        Qt uses a painter-canvas model:
        1. Create QPainter with target (self = this widget)
        2. Configure painter (brush, pen, hints)
        3. Draw shapes/paths/text
        4. Painter auto-destructs at end of method

        Rounded Rectangle Path:
        -----------------------
        ```python
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 20, 20)
        ```

        The 20, 20 are corner radii (x, y). Using equal values gives
        circular corners.

        Antialiasing:
        -------------
        ```python
        painter.setRenderHint(QPainter.Antialiasing)
        ```

        Without this, curves look jagged (aliased). Antialiasing blends
        edge pixels for smooth appearance. Slight performance cost.

        Semi-Transparent Fill:
        ----------------------
        QColor(255, 255, 255, 220) = RGBA white with ~86% opacity.
        This creates the frosted-glass effect over desktop content.
        """
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 20, 20)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)
