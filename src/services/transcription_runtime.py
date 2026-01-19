"""
Audio recording and transcription thread for Vociferous.

Captures audio from microphone, applies Voice Activity Detection (VAD),
and sends audio to the Whisper transcription engine via QThread.
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal
from threading import Event

from src.core_runtime.client import EngineClient
from src.core_runtime.types import EngineState, TranscriptionResult

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Backend Compatibility Aliases
ThreadState = EngineState
ThreadResult = TranscriptionResult


class TranscriptionRuntime(QThread):
    """
    QThread wrapper around the IPC EngineClient.

    Acts as a bridge between Qt signals and the IPC Client.
    Blocks in run() to maintain QThread lifecycle semantics.
    """

    resultReady = pyqtSignal(ThreadResult)
    audioLevelUpdated = pyqtSignal(float)
    audioSpectrumUpdated = pyqtSignal(list)

    def __init__(self, local_model: "WhisperModel | None" = None) -> None:
        """Initialize the runtime thread."""
        super().__init__()
        self._completion_event = Event()

        # Instantiate IPC Client
        self.client = EngineClient(
            on_result=self._on_client_result,
            on_audio_level=self.audioLevelUpdated.emit,
            on_status=self._on_client_status,
        )

    def _on_client_result(self, result: TranscriptionResult):
        self.resultReady.emit(result)

        if result.state in (EngineState.COMPLETE, EngineState.ERROR):
            self._completion_event.set()

    def _on_client_status(self, status: str):
        logger.info(f"Engine Status: {status}")

    def stop_recording(self) -> None:
        """Stop the current recording session."""
        self.client.stop_session()

    def stop(self) -> None:
        """Stop the entire thread execution."""
        # Force completion event to unblock run() if needed
        self._completion_event.set()

        self.client.shutdown()

        # Signal IDLE state to UI (Legacy behavior)
        self.resultReady.emit(ThreadResult(state=ThreadState.IDLE))

        self.wait()

    def run(self) -> None:
        """
        Main thread execution: Manage IPC session lifecycle.
        """
        self._completion_event.clear()

        try:
            # 1. Connect (if needed) and Start Session
            # Blocks briefly to spawn process if not running
            self.client.start_session()

            # 2. Waiting Loop
            # We block here so QThread.isRunning() remains True until the engine finishes
            self._completion_event.wait()

        except Exception as e:
            logger.exception("Runtime Wrapper Failure")
            self.resultReady.emit(
                ThreadResult(
                    state=EngineState.ERROR, error_message=f"Runtime Error: {e}"
                )
            )
