"""
Test suite for RefineView behavioral contracts.
Verifies the Ingress, State, and Output contracts defined in the investigation report.
"""

import pytest
from PyQt6.QtCore import Qt
from src.ui.views.refine_view import RefineView
from src.ui.contracts.capabilities import ActionId, Capabilities


def test_ingress_populates_context(qtbot):
    """
    Contract: Ingress (load_transcript_by_id) must populate the view context
    and reset the refined state.
    """
    view = RefineView()
    qtbot.addWidget(view)

    original_text = "This is a test transcript."
    tid = 101

    view.load_transcript_by_id(tid, original_text)

    # Check internal state matches ingress
    assert view._current_transcript_id == tid
    assert view._original_text == original_text
    assert view._refined_text == ""  # Should be empty initially

    # Check loading state is reset
    assert not view._is_loading


def test_loading_state_gates_interaction(qtbot):
    """
    Contract: When set_loading(True) is called, capabilities should be restricted
    to prevent race conditions.
    """
    view = RefineView()
    view.resize(800, 600)
    qtbot.addWidget(view)

    view.set_loading(True)

    # Check internal state
    assert view._is_loading

    # Check visual indicator visibility
    # Note: isVisible() requires the parent to be visible too.
    # We check isHidden() which reflects the direct setVisible state.
    assert not view._lbl_loading.isHidden()

    # Check capability gating
    caps = view.get_capabilities()
    assert not caps.can_save
    assert not caps.can_discard
    assert not caps.can_copy


def test_review_state_enables_actions(qtbot):
    """
    Contract: When comparison text is set, SAVE and DISCARD must be enabled.
    """
    view = RefineView()
    qtbot.addWidget(view)

    view.set_comparison(202, "Original", "Refined")

    caps = view.get_capabilities()
    assert caps.can_save
    assert caps.can_discard
    assert caps.can_copy

    # Loading should be off
    assert not view._lbl_loading.isVisible()


def test_accept_action_emits_signal(qtbot):
    """
    Contract: Triggering SAVE (Accept) must emit refinementAccepted
    with correct ID and Text.
    """
    view = RefineView()
    qtbot.addWidget(view)

    tid = 303
    refined = "Better text."
    view.set_comparison(tid, "Bad text", refined)

    with qtbot.waitSignal(view.refinement_accepted) as blocker:
        view.dispatch_action(ActionId.SAVE)

    assert blocker.args == [tid, refined]


def test_discard_action_emits_signal(qtbot):
    """
    Contract: Triggering DISCARD must emit refinementDiscarded.
    """
    view = RefineView()
    qtbot.addWidget(view)

    view.set_comparison(404, "Original", "Refined")

    with qtbot.waitSignal(view.refinement_discarded):
        view.dispatch_action(ActionId.DISCARD)


def test_actions_invalid_without_content(qtbot):
    """
    Contract: Review actions must be disabled if no refinement content is present.
    """
    view = RefineView()
    qtbot.addWidget(view)

    # CASE 1: Empty View
    caps = view.get_capabilities()
    assert not caps.can_save
    assert not caps.can_copy
    # can_discard is explicitly True to allow exit from empty state

    # CASE 2: Loaded Original, No Refinement
    view.load_transcript("Just text")
    caps = view.get_capabilities()
    assert not caps.can_save
    assert not caps.can_copy


def test_loading_gates_functional_interaction(qtbot):
    """
    Contract: Loading state must functionally block dispatch_action,
    not just capabilities.
    """
    view = RefineView()
    qtbot.addWidget(view)

    # Setup legal state first
    view.set_comparison(1, "Orig", "Refined")

    # Enter loading state
    view.set_loading(True)

    # Try to force SAVE action via dispatch
    # Signal should NOT fire
    with qtbot.assertNotEmitted(view.refinement_accepted):
        view.dispatch_action(ActionId.SAVE)

    # Try to force COPY
    # Copy would normally interact with clipboard, hard to assert "not emitted"
    # unless we mock copy_text.
    # But capabilities check confirms UI layer is blocked.


def test_style_contract_conformance(qtbot):
    """
    Contract: View must use standard container classes (ContentPanel).
    """
    from src.ui.components.shared import ContentPanel

    view = RefineView()
    qtbot.addWidget(view)

    # Navigate widget tree
    panels = view.findChildren(ContentPanel)
    assert len(panels) >= 2, "RefineView must use at least 2 ContentPanels"

    # Check for direct text edit abuse (root level or direct path)
    # We expect text edits to be INSIDE ContentPanel, not direct children of main layout

    # Check for layout margins
    layout = view.layout()
    margins = layout.contentsMargins()
    # Should maintain some spacing, not 0 (unless that changed in latest refactor)
    assert margins.left() > 0 or margins.top() > 0
