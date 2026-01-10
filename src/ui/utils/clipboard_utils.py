"""Clipboard utility functions for UI components."""


def copy_text(text: str) -> None:
    """
    Copy text to the system clipboard.

    Args:
        text: Text to copy to clipboard
    """
    from PyQt6.QtWidgets import QApplication
    
    clipboard = QApplication.clipboard()
    if clipboard:
        clipboard.setText(text)
