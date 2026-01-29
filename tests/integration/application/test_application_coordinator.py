import pytest
from unittest.mock import MagicMock, patch, call
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from src.core.application_coordinator import ApplicationCoordinator
from src.ui.interaction.intents import (
    BeginRecordingIntent,
    StopRecordingIntent,
    ToggleRecordingIntent,
)


@pytest.fixture
def mock_qapp():
    # If QApplication doesn't exist, create it (needed for signals to work)
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


@pytest.fixture
def coordinator_patches():
    """Patches all dependencies for ApplicationCoordinator."""
    with (
        patch("src.core.application_coordinator.ConfigManager") as mock_config,
        patch("src.core.application_coordinator.KeyListener") as mock_listener,
        patch("src.core.application_coordinator.HistoryManager") as mock_history,
        patch("src.core.application_coordinator.StateManager") as mock_state,
        patch("src.core.application_coordinator.MainWindow") as mock_window,
        patch("src.core.application_coordinator.SystemTrayManager") as mock_tray,
        patch("src.core.application_coordinator.SLMService") as mock_slm,
        patch("src.core.application_coordinator.EngineClient") as mock_engine_client,
    ):
        # Make SystemTrayManager.build_icon() return a valid QIcon
        mock_tray.build_icon.return_value = QIcon()

        yield {
            "config": mock_config,
            "listener": mock_listener,
            "history": mock_history,
            "state": mock_state,
            "window": mock_window,
            "tray": mock_tray,
            "slm": mock_slm,
            "engine_client": mock_engine_client,
        }


@pytest.fixture
def coordinator(mock_qapp, coordinator_patches):
    coord = ApplicationCoordinator(mock_qapp)
    yield coord
    # Ensure any threads are cleaned up if start() was called
    coord.cleanup()


def test_initialization_order(mock_qapp, coordinator_patches):
    """
    Verify strict initialization order: config -> logging -> core services -> UI.
    """
    coord = ApplicationCoordinator(mock_qapp)
    try:
        coord.start()

        # Config must be initialized
        coordinator_patches["config"].initialize.assert_called()

        # History initialized
        coordinator_patches["history"].assert_called()

        # MainWindow initialized
        coordinator_patches["window"].assert_called()

        # SLM Service initialized
        coordinator_patches["slm"].assert_called()
    finally:
        coord.cleanup()


def test_service_wiring(coordinator, coordinator_patches):
    """
    Verify signal connections between components.
    """
    coordinator.start()

    # Retrieve the mock instances created during start()
    mock_window_instance = coordinator_patches["window"].return_value
    mock_listener_instance = coordinator_patches["listener"].return_value

    # Check that MainWindow signals are connected
    # We check if connect was called on the signals.
    # Note: signals are attributes of the instance.
    # assert mock_window_instance.intent_dispatched.connect.called # Now uses CommandBus
    assert mock_window_instance.motd_refresh_requested.connect.called

    # Check KeyListener started
    mock_listener_instance.start.assert_called()


def test_intent_routing(coordinator, coordinator_patches):
    """
    Verify intents trigger correct actions.
    """
    # Need to simulate start() to wire things up, or manually wire
    coordinator.start()

    # 1. Test BeginRecordingIntent -> start_result_thread
    with patch.object(coordinator, "start_result_thread") as mock_start:
        coordinator._on_intent(BeginRecordingIntent())
        mock_start.assert_called_once()

    # 2. Test StopRecordingIntent -> _stop_recording_from_ui
    with patch.object(coordinator, "_stop_recording_from_ui") as mock_stop:
        coordinator._on_intent(StopRecordingIntent())
        mock_stop.assert_called_once()


def test_cleanup(coordinator, coordinator_patches):
    """
    Verify graceful shutdown.
    """
    # Start to ensure things are set up
    coordinator.start()

    coordinator_patches["listener"].return_value

    # Mock the thread methods since QThread is real (or we can patch it too, but let's assume it's created)
    # The coordinator creates a QThread. We should probably mock quit/wait on it.
    # We can patch QThread in the module if we want strict control.
    with patch("src.core.application_coordinator.QThread") as mock_qthread_cls:
        mock_thread_instance = mock_qthread_cls.return_value

        # Reset coordinator to use this mock thread
        coord = ApplicationCoordinator(QApplication.instance())
        try:
            coord.start()

            coord.cleanup()

            coordinator_patches["listener"].return_value.stop.assert_called()

            # Check thread quit
            mock_thread_instance.quit.assert_called()
            mock_thread_instance.wait.assert_called()
        finally:
            coord.cleanup()


def test_engine_no_respawn_during_shutdown(qapp):
    """Test that engine does not respawn when killed during intentional shutdown."""
    from unittest.mock import patch
    from src.core.application_coordinator import ApplicationCoordinator
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()

    with (
        patch("src.core.application_coordinator.QThread"),
        patch("src.core.application_coordinator.KeyListener"),
        patch("src.core.application_coordinator.ConfigManager"),
        patch("src.core.application_coordinator.StateManager"),
        patch("src.core.application_coordinator.HistoryManager"),
        patch("src.core.application_coordinator.MainWindow"),
        patch("src.core.application_coordinator.SystemTrayManager") as mock_tray,
        patch("src.core.application_coordinator.SLMService"),
        patch(
            "src.core.application_coordinator.EngineClient"
        ) as mock_engine_client_cls,
    ):
        # Make SystemTrayManager.build_icon() return a valid QIcon
        mock_tray.build_icon.return_value = QIcon()

        mock_engine_client = mock_engine_client_cls.return_value

        coord = ApplicationCoordinator(app)

        # Start the coordinator
        coord.start()

        # Simulate shutdown
        coord.cleanup()

        # Verify shutdown was called on engine client
        mock_engine_client.shutdown.assert_called_once()


def test_hotkey_on_activation_toggle_mode(coordinator, coordinator_patches):
    """Verify on_activation dispatches ToggleRecordingIntent in toggle mode."""
    coordinator.start()
    mock_window = coordinator_patches["window"].return_value
    coordinator_patches["config"].get_config_value.return_value = "press_to_toggle"

    coordinator.on_activation()

    # Check if dispatch_intent was called with ToggleRecordingIntent
    args, _ = mock_window.dispatch_intent.call_args
    assert isinstance(args[0], ToggleRecordingIntent)


def test_hotkey_on_activation_ptt_mode(coordinator, coordinator_patches):
    """Verify on_activation dispatches BeginRecordingIntent in PTT mode."""
    coordinator.start()
    mock_window = coordinator_patches["window"].return_value
    coordinator_patches["config"].get_config_value.return_value = "push_to_talk"

    coordinator.on_activation()

    # Check if dispatch_intent was called with BeginRecordingIntent
    args, _ = mock_window.dispatch_intent.call_args
    assert isinstance(args[0], BeginRecordingIntent)


def test_hotkey_on_deactivation_toggle_mode(coordinator, coordinator_patches):
    """Verify on_deactivation does nothing in toggle mode."""
    coordinator.start()
    mock_window = coordinator_patches["window"].return_value
    coordinator_patches["config"].get_config_value.return_value = "press_to_toggle"

    # Reset mock to clear calls from initialization or previous actions
    mock_window.dispatch_intent.reset_mock()

    coordinator.on_deactivation()

    # Should NOT dispatch any intent
    mock_window.dispatch_intent.assert_not_called()


def test_hotkey_on_deactivation_ptt_mode(coordinator, coordinator_patches):
    """Verify on_deactivation dispatches StopRecordingIntent in PTT mode."""
    coordinator.start()
    mock_window = coordinator_patches["window"].return_value
    coordinator_patches["config"].get_config_value.return_value = "push_to_talk"

    # Reset mock
    mock_window.dispatch_intent.reset_mock()

    coordinator.on_deactivation()

    # Should dispatch StopRecordingIntent
    args, _ = mock_window.dispatch_intent.call_args
    assert isinstance(args[0], StopRecordingIntent)


def test_handle_transcription_result_save_failure_shows_dialog_and_copies(coordinator, coordinator_patches):
    """When history save fails, show dialog with retry and copy transcript to clipboard."""
    from src.core.exceptions import DatabaseError
    from src.core_runtime.types import TranscriptionResult, EngineState

    coordinator.start()

    mock_history = coordinator_patches["history"].return_value
    mock_history.add_entry.side_effect = DatabaseError("DB fail")

    result = TranscriptionResult(
        state=EngineState.COMPLETE, text="A B C", duration_ms=123, speech_duration_ms=45
    )

    with (
        patch("src.ui.widgets.dialogs.error_dialog.show_error_dialog") as mock_show,
        patch("src.ui.utils.clipboard_utils.copy_text") as mock_copy,
    ):
        coordinator._handle_transcription_result(result)

        mock_show.assert_called_once()
        _, kwargs = mock_show.call_args
        assert "retry_callback" in kwargs and kwargs["retry_callback"] is not None

        mock_copy.assert_called_once_with("A B C")

        main_window = coordinator_patches["window"].return_value
        main_window.on_transcription_complete.assert_not_called()


def test_handle_transcription_result_retry_callback_succeeds(coordinator, coordinator_patches):
    """Retry callback should re-attempt save and call on_transcription_complete on success."""
    from src.core.exceptions import DatabaseError
    from src.database.dtos import HistoryEntry
    from src.core_runtime.types import TranscriptionResult, EngineState

    coordinator.start()

    mock_history = coordinator_patches["history"].return_value

    success_entry = HistoryEntry(
        timestamp="2025-01-01T12:00:00", text="A B C", duration_ms=123
    )

    mock_history.add_entry.side_effect = [DatabaseError("DB fail"), success_entry]

    result = TranscriptionResult(
        state=EngineState.COMPLETE, text="A B C", duration_ms=123, speech_duration_ms=45
    )

    with (
        patch("src.ui.widgets.dialogs.error_dialog.show_error_dialog") as mock_show,
        patch("src.ui.utils.clipboard_utils.copy_text"),
    ):
        coordinator._handle_transcription_result(result)

        mock_show.assert_called_once()
        retry_cb = mock_show.call_args.kwargs.get("retry_callback")
        assert callable(retry_cb)

        # Invoke the retry callback; should attempt to save again and succeed
        retry_cb()

        assert mock_history.add_entry.call_count == 2
        main_window = coordinator_patches["window"].return_value
        main_window.on_transcription_complete.assert_called_once_with(success_entry)


def test_start_handles_history_init_failure_shows_dialog_and_retries(mock_qapp):
    """If HistoryManager initialization fails during start(), show a retry dialog that allows re-initialization."""
    # Configure HistoryManager to fail first, then succeed
    hist_side = [Exception("init fail"), MagicMock()]

    with (
        patch("src.core.application_coordinator.HistoryManager", side_effect=hist_side),
        patch("src.ui.widgets.dialogs.error_dialog.show_error_dialog") as mock_show,
        patch("src.core.application_coordinator.StateManager"),
    ):
        coord = ApplicationCoordinator(mock_qapp)

        # First start: init should fail and show dialog
        coord.start()
        mock_show.assert_called_once()

        retry_cb = mock_show.call_args.kwargs.get("retry_callback")
        assert callable(retry_cb)

        # Before retry, history_manager should not be set
        assert getattr(coord, "history_manager", None) is None

        # Simulate user pressing Retry on the dialog
        retry_cb()

        # After retry, history_manager should be initialized (side_effect second value)
        assert getattr(coord, "history_manager", None) is not None
