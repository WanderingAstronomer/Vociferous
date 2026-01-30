"""
Test Onboarding Invariants.

Enforces:
1. Greeting Logic (Time-awareness, Easter Egg, Personalization).
2. Onboarding Wizard Gates (Navigation constraints).
3. Config Persistence on Completion.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.ui.components.workspace.header import _get_greeting
from src.ui.components.onboarding.onboarding_window import OnboardingWindow
from src.ui.components.onboarding.pages import IdentityPage, RefinementPage
from src.core.config_manager import ConfigManager

# --- Greeting Invariants ---


@patch("src.ui.components.workspace.header.datetime")
@patch("src.core.config_manager.ConfigManager.get_config_value")
def test_greeting_night_owl(mock_config, mock_datetime):
    """Invariant: 00:00-05:00 triggers 'Hey there, night owl!'"""
    mock_datetime.now.return_value.hour = 2
    mock_config.return_value = ""  # No name behavior check first

    greeting = _get_greeting()
    assert greeting == "Hey there, night owl!"


@patch("src.ui.components.workspace.header.datetime")
@patch("src.core.config_manager.ConfigManager.get_config_value")
def test_greeting_morning(mock_config, mock_datetime):
    """Invariant: 05:00-11:59 triggers 'Good morning', with simple punctuation if no name."""
    mock_datetime.now.return_value.hour = 9
    mock_config.return_value = ""

    greeting = _get_greeting()
    assert greeting == "Good morning."


@patch("src.ui.components.workspace.header.datetime")
@patch("src.core.config_manager.ConfigManager.get_config_value")
def test_greeting_personalization(mock_config, mock_datetime):
    """Invariant: Name is appended with comma and period."""
    mock_datetime.now.return_value.hour = 14  # Afternoon
    mock_config.return_value = "Andrew"

    greeting = _get_greeting()
    assert greeting == "Good afternoon, Andrew."


# --- Onboarding UI Invariants ---


@pytest.fixture
def onboarding_window(qtbot):
    """Fixture for OnboardingWindow with mocked dependencies."""
    mock_listener = MagicMock()
    window = OnboardingWindow(key_listener=mock_listener)
    window.show()
    qtbot.addWidget(window)
    return window


def test_onboarding_identity_gate(qtbot):
    """Invariant: Identity page is optional (always complete)."""
    page = IdentityPage()
    qtbot.addWidget(page)

    # Initially empty -> Complete (Optional)
    assert page.is_complete()

    # Type name -> Complete
    page.name_input.setText("User")
    assert page.is_complete()


def test_onboarding_refinement_gate(qtbot):
    """Invariant: Refinement page requires at least one model selection."""

    # Mock Models to ensure Pills are generated
    mock_model = MagicMock()
    mock_model.id = "test-model-1"
    mock_model.name = "Test Model"
    mock_model.required_vram_mb = 1000

    with patch.dict("src.core.model_registry.MODELS", {mock_model.id: mock_model}):
        page = RefinementPage()
        qtbot.addWidget(page)

        # Initially incomplete (no models selected)
        assert not page.is_complete()
        assert len(page.selected_models) == 0

        # Select a model by clicking the pill
        first_pill = list(page.model_pills.values())[0]
        qtbot.mouseClick(first_pill, Qt.MouseButton.LeftButton)

        # Now complete
        assert page.is_complete(), f"Expected complete but got {page.selected_models}"
        assert len(page.selected_models) == 1


@patch("src.core.config_manager.ConfigManager.set_config_value")
@patch("src.core.config_manager.ConfigManager.save_config")
def test_onboarding_finish_action(mock_save, mock_set, onboarding_window, qtbot):
    """Invariant: Finishing onboarding persists 'onboarding_completed' = True."""
    # Force state to last page and simulate finish
    # We can call the internal method for testing specific logic
    onboarding_window._finish_onboarding()

    mock_set.assert_any_call(True, "user", "onboarding_completed")
    mock_save.assert_called_once()
    assert onboarding_window.result() == OnboardingWindow.DialogCode.Accepted
