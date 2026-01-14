"""
Tests for Dialog Invariants.
"""
import pytest
from PyQt6.QtWidgets import QApplication, QPushButton

from ui.widgets.dialogs.error_dialog import ErrorDialog

pytestmark = pytest.mark.ui_dependent

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    yield app

class TestErrorDialogInvariants:
    def test_copy_details_affordance(self, qapp):
        """
        Invariant 11.2: Error Dialog Rules.
        Must expose a 'Copy details' affordance that copies payload to clipboard.
        """
        modal_details = "Specific stack trace payload for testing"
        dialog = ErrorDialog(
            parent=None,
            title="Test Error",
            message="Error message",
            details=modal_details,
        )

        # 1. Verify existence of user-facing affordance
        # Invariant 11.2: Must use deterministic ID
        dialog.show()
        qapp.processEvents()
        
        copy_btn = dialog.findChild(QPushButton, "errorDialogCopy")
        
        assert copy_btn is not None, "Invariant Violation: No 'Copy' button found with ID 'errorDialogCopy'"
        assert copy_btn.isVisible(), "Copy button must be visible to user"
        
        # 2. Verify clipboard effect
        clipboard = QApplication.clipboard()
        clipboard.clear()
        
        # Trigger click and process events
        copy_btn.click()
        qapp.processEvents()
        
        # Check payload
        clipboard_text = clipboard.text()
        assert modal_details in clipboard_text, "Clipboard text missing details payload"
        
        # Also verification of Invariant 11.2.1: Human readable msg
        assert "Error message" in clipboard_text
        
        dialog.close()
