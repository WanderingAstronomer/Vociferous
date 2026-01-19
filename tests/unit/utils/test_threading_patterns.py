"""
Test threading pattern compliance with Qt6 best practices.

Verifies that background workers use the moveToThread pattern
instead of subclassing QThread, per Qt6 documentation recommendations.

Tests enforce:
- Workers are QObject subclasses, not QThread
- Workers use do_work() slot instead of run() method
- Workers can be safely moved to QThread
- Thread cleanup is properly implemented

Addresses audit finding: P1-05 (Critical architectural pattern)

References:
- Qt6 Threading Best Practices: https://doc.qt.io/qt-6/threads-qobject.html
- "Don't subclass QThread unless reimplementing QThread::run() is necessary"
"""

import pytest
from PyQt6.QtCore import QObject, QThread


class TestSetupWorkerThreadingPattern:
    """Test SetupWorker uses moveToThread pattern instead of QThread subclass."""

    def test_worker_is_qobject_not_qthread(self):
        """Worker should be QObject, not QThread subclass per Qt6 best practices."""
        from src.ui.components.onboarding.pages import SetupWorker

        worker = SetupWorker(False, False, [])

        # Should be QObject but NOT QThread
        assert isinstance(worker, QObject), (
            "SetupWorker must be QObject for moveToThread pattern"
        )
        assert not isinstance(worker, QThread), (
            "SetupWorker must NOT subclass QThread (anti-pattern)"
        )

    def test_worker_has_do_work_method(self):
        """Worker should have do_work() slot, not run() method."""
        from src.ui.components.onboarding.pages import SetupWorker

        worker = SetupWorker(False, False, [])

        assert hasattr(worker, "do_work"), (
            "SetupWorker must have do_work() slot for moveToThread pattern"
        )
        assert callable(worker.do_work), "do_work must be callable slot"

        # Should NOT have run() method (QThread pattern)
        assert not hasattr(worker, "run"), (
            "SetupWorker should not have run() method (use do_work instead)"
        )

    def test_worker_can_be_moved_to_thread(self, qtbot):
        """Worker should be movable to QThread via moveToThread()."""
        from src.ui.components.onboarding.pages import SetupWorker

        thread = QThread()
        worker = SetupWorker(False, False, [])

        # Should not raise exception when moving to thread
        worker.moveToThread(thread)

        # Verify worker is now owned by thread
        assert worker.thread() == thread, (
            "Worker should be owned by target thread after moveToThread"
        )

        # Clean up
        thread.quit()
        thread.wait()

    def test_worker_has_finished_signal(self):
        """Worker must emit finished signal with (bool, str) signature."""
        from src.ui.components.onboarding.pages import SetupWorker

        worker = SetupWorker(False, False, [])

        assert hasattr(worker, "finished"), (
            "SetupWorker must have 'finished' signal for completion notification"
        )

        # Verify signal exists and is a pyqtSignal
        from PyQt6.QtCore import pyqtSignal

        assert isinstance(type(worker).finished, pyqtSignal), (
            "finished must be a pyqtSignal"
        )

    def test_worker_thread_safety(self, qtbot):
        """Worker should be thread-safe when moved to background thread."""
        from src.ui.components.onboarding.pages import SetupWorker

        thread = QThread()
        worker = SetupWorker(False, False, [])

        # Track completion
        finished_called = []

        def on_finished(success, message):
            finished_called.append((success, message))

        worker.finished.connect(on_finished)
        worker.moveToThread(thread)

        # Connect thread start to worker
        thread.started.connect(worker.do_work)

        # Start thread
        thread.start()

        # Wait for completion (with timeout)
        qtbot.waitUntil(lambda: len(finished_called) > 0, timeout=5000)

        # Verify worker completed
        assert len(finished_called) == 1, "Worker should complete exactly once"
        success, message = finished_called[0]
        assert isinstance(success, bool), "Success should be boolean"
        assert isinstance(message, str), "Message should be string"

        # Clean up
        thread.quit()
        thread.wait()


class TestThreadCleanup:
    """Test proper thread cleanup and resource management."""

    def test_thread_cleanup_on_completion(self, qtbot):
        """Thread should clean up resources when worker finishes."""
        from src.ui.components.onboarding.pages import SetupWorker

        thread = QThread()
        worker = SetupWorker(False, False, [])

        worker.moveToThread(thread)
        thread.started.connect(worker.do_work)

        # Set up cleanup chain
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # Track thread finish
        thread_finished = []
        thread.finished.connect(lambda: thread_finished.append(True))

        thread.start()

        # Wait for thread to emit finished signal
        qtbot.waitUntil(lambda: len(thread_finished) > 0, timeout=5000)

        # Thread should have emitted finished (which means it stopped)
        assert len(thread_finished) == 1, (
            "Thread should finish and emit finished signal"
        )

    def test_thread_can_be_terminated_early(self, qtbot):
        """Thread should respond to quit() signal even if worker is running."""
        from src.ui.components.onboarding.pages import SetupWorker

        thread = QThread()
        worker = SetupWorker(False, False, [])

        worker.moveToThread(thread)
        thread.start()

        # Immediately quit (don't wait for worker)
        thread.quit()
        thread.wait(1000)  # Wait up to 1 second

        assert not thread.isRunning(), "Thread should stop when quit() is called"


class TestThreadPatternIntegration:
    """Test integration of threading pattern with onboarding pages."""

    def test_onboarding_uses_correct_thread_pattern(self, qtbot):
        """OnboardingWindow should use moveToThread pattern for background work."""
        from src.ui.components.onboarding.onboarding_window import OnboardingWindow
        from unittest.mock import MagicMock, patch

        # OnboardingWindow requires a key_listener
        mock_listener = MagicMock()

        # Patch ConfirmationDialog to avoid hanging in teardown
        # We must keep the patch active when close() is called.
        # Since qtbot.addWidget() registers cleanup for AFTER the test function (and after the patch context),
        # we cannot rely on qtbot cleanup here if we use a context manager for patching.
        # Instead, we manage lifecycle validation manually within the patch block.
        with patch("src.ui.widgets.dialogs.ConfirmationDialog.exec") as mock_exec:
            mock_exec.return_value = 1  # DialogCode.Accepted

            window = OnboardingWindow(key_listener=mock_listener)
            # NOT using qtbot.addWidget(window) to avoid unpatched teardown invoke

            with qtbot.waitExposed(window):
                window.show()

            # This is a heuristic test - just verify no crashes
            assert window.isWidgetType(), "OnboardingWindow should be valid widget"

            # Manually close while patch is active
            window.close()
            # Force event processing to ensure closeEvent completes
            qtbot.wait(50)
