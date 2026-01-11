"""
Error dialog for displaying errors with stack traces.

Provides a user-friendly error display with:
- Clear error message
- Expandable details section for stack traces
- Copy to clipboard functionality
- View logs button
- Optional retry callback
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.constants import MINOR_GAP, Typography, Colors
from ui.widgets.styled_button import ButtonStyle, StyledButton
from ui.widgets.dialogs.custom_dialog import StyledDialog


class ErrorDialog(StyledDialog):
    """
    Error dialog with expandable stack trace and action buttons.

    Features:
    - Error icon and message display
    - Expandable "Show Details" section with stack trace
    - "Copy to Clipboard" button for bug reports
    - "View Logs" button to open log file
    - Optional "Retry" button with callback
    - Automatic error logging when displayed
    """

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        details: str = "",
        retry_callback: Callable[[], None] | None = None,
        show_view_logs: bool = True,
    ) -> None:
        """
        Create an error dialog.

        Args:
            parent: Parent widget
            title: Dialog title
            message: User-friendly error message
            details: Technical details (stack trace)
            retry_callback: Optional callback for Retry button
            show_view_logs: Whether to show the View Logs button
        """
        super().__init__(parent, title)
        
        self._message = message
        self._details = details
        self._retry_callback = retry_callback
        self._show_view_logs = show_view_logs
        self._details_visible = False

        self._setup_error_ui()
        self._log_error()

    def _setup_error_ui(self) -> None:
        """Set up the error dialog UI."""
        self.setObjectName("errorDialog")

        # Error icon and message row
        message_row = QHBoxLayout()
        message_row.setSpacing(MINOR_GAP)

        # Error indicator (colored label instead of icon)
        error_indicator = QLabel("⚠")
        error_indicator.setObjectName("errorDialogIcon")
        error_indicator.setStyleSheet(f"""
            QLabel#errorDialogIcon {{
                color: {Colors.DESTRUCTIVE};
                font-size: {Typography.FONT_SIZE_XL}px;
                font-weight: {Typography.FONT_WEIGHT_EMPHASIS};
                padding: 0;
                margin: 0;
            }}
        """)
        error_indicator.setFixedWidth(40)
        error_indicator.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        message_row.addWidget(error_indicator)

        # Message text
        message_label = QLabel(self._message)
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        message_label.setObjectName("errorDialogMessage")
        message_row.addWidget(message_label, 1)

        self.content_layout.addLayout(message_row)

        # Details section (initially hidden)
        if self._details:
            self._setup_details_section()

        # Action buttons row
        self._setup_action_buttons()

        # Standard buttons (OK, Retry)
        self._setup_dialog_buttons()

        self._finalize_size(min_width=500)

    def _setup_details_section(self) -> None:
        """Set up the expandable details section."""
        # Toggle button
        self.details_toggle = StyledButton("▶ Show Details", ButtonStyle.SECONDARY)
        self.details_toggle.setObjectName("errorDialogToggle")
        self.details_toggle.clicked.connect(self._toggle_details)
        self.details_toggle.setStyleSheet(f"""
            QPushButton#errorDialogToggle {{
                background-color: transparent;
                color: {Colors.TEXT_SECONDARY};
                border: none;
                text-align: left;
                padding: 4px 8px;
                font-size: {Typography.SMALL_SIZE}pt;
            }}
            QPushButton#errorDialogToggle:hover {{
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        self.content_layout.addWidget(self.details_toggle)

        # Details container (hidden by default)
        self.details_container = QWidget()
        self.details_container.setObjectName("errorDialogDetailsContainer")
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, MINOR_GAP, 0, 0)
        details_layout.setSpacing(MINOR_GAP)

        # Stack trace text area
        self.details_text = QPlainTextEdit()
        self.details_text.setObjectName("errorDialogDetails")
        self.details_text.setReadOnly(True)
        self.details_text.setPlainText(self._details)
        self.details_text.setMinimumHeight(120)
        self.details_text.setMaximumHeight(200)
        
        # Monospace font for stack traces
        mono_font = QFont("monospace")
        mono_font.setPointSize(Typography.SMALL_SIZE)
        self.details_text.setFont(mono_font)
        
        details_layout.addWidget(self.details_text)

        self.details_container.hide()
        self.content_layout.addWidget(self.details_container)

    def _setup_action_buttons(self) -> None:
        """Set up copy and view logs buttons."""
        action_row = QHBoxLayout()
        action_row.setSpacing(MINOR_GAP)

        # Copy to clipboard button
        if self._details:
            copy_btn = StyledButton("📋 Copy Details", ButtonStyle.SECONDARY)
            copy_btn.setObjectName("errorDialogCopy")
            copy_btn.clicked.connect(self._copy_to_clipboard)
            copy_btn.setMinimumHeight(32)
            action_row.addWidget(copy_btn)

        # View logs button
        if self._show_view_logs:
            view_logs_btn = StyledButton("📁 View Logs", ButtonStyle.SECONDARY)
            view_logs_btn.setObjectName("errorDialogViewLogs")
            view_logs_btn.clicked.connect(self._view_logs)
            view_logs_btn.setMinimumHeight(32)
            action_row.addWidget(view_logs_btn)

        action_row.addStretch()
        self.content_layout.addLayout(action_row)

    def _setup_dialog_buttons(self) -> None:
        """Set up OK and optional Retry buttons."""
        self.button_layout.addStretch()

        # Retry button (if callback provided)
        if self._retry_callback:
            retry_btn = self.add_button("Retry", "secondary", self._on_retry)
            retry_btn.setMinimumWidth(100)

        # OK button
        ok_btn = self.add_button("OK", "primary", self.accept)
        ok_btn.setMinimumWidth(100)
        ok_btn.setFocus()

    def _toggle_details(self) -> None:
        """Toggle the details section visibility."""
        self._details_visible = not self._details_visible
        self.details_container.setVisible(self._details_visible)

        if self._details_visible:
            self.details_toggle.setText("▼ Hide Details")
        else:
            self.details_toggle.setText("▶ Show Details")

        # Adjust dialog size
        self.adjustSize()

    def _copy_to_clipboard(self) -> None:
        """Copy error details to clipboard."""
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            full_text = f"Error: {self._message}\n\nDetails:\n{self._details}"
            clipboard.setText(full_text)

    def _view_logs(self) -> None:
        """Open the log file in the system editor."""
        try:
            from ui.utils.error_handler import ErrorLogger
            ErrorLogger.open_log_file()
        except Exception:
            # If we can't open logs, at least don't crash
            pass

    def _on_retry(self) -> None:
        """Handle retry button click."""
        self.accept()
        if self._retry_callback:
            try:
                self._retry_callback()
            except Exception:
                # Don't let retry callback errors crash the app
                pass

    def _log_error(self) -> None:
        """Log the error when the dialog is shown."""
        try:
            from ui.utils.error_handler import get_error_logger
            error_logger = get_error_logger()
            error_logger.log_error(
                f"Error dialog shown: {self._message}",
                context="ErrorDialog",
            )
        except Exception:
            # Don't fail if logging fails
            pass


def show_error_dialog(
    title: str,
    message: str,
    details: str = "",
    parent: QWidget | None = None,
    retry_callback: Callable[[], None] | None = None,
) -> None:
    """
    Convenience function to show an error dialog.

    Args:
        title: Dialog title
        message: User-friendly error message
        details: Technical details (stack trace)
        parent: Parent widget (uses active window if None)
        retry_callback: Optional callback for Retry button
    """
    # Get parent window if not specified
    if parent is None:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            # Try to get the active window
            for widget in QApplication.topLevelWidgets():
                if widget.isActiveWindow():
                    parent = widget
                    break

    dialog = ErrorDialog(
        parent=parent,
        title=title,
        message=message,
        details=details,
        retry_callback=retry_callback,
    )
    dialog.exec()


def show_warning_dialog(
    title: str,
    message: str,
    details: str = "",
    parent: QWidget | None = None,
) -> None:
    """
    Convenience function to show a warning dialog.

    Similar to error dialog but without the error indicator styling.

    Args:
        title: Dialog title
        message: Warning message
        details: Optional additional details
        parent: Parent widget
    """
    dialog = ErrorDialog(
        parent=parent,
        title=title,
        message=message,
        details=details,
        show_view_logs=False,
    )
    dialog.exec()
