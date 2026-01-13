"""
Audio recording and transcription thread for Vociferous.

Captures audio from microphone, applies Voice Activity Detection (VAD),
and sends audio to the Whisper transcription engine via QThread.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from PyQt6.QtCore import QMutex, QThread, pyqtSignal

from services.audio_service import AudioService
from transcription import transcribe
from utils import ConfigManager

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class ThreadState(Enum):
    """Thread execution states for unified result signaling."""

    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    COMPLETE = auto()
    ERROR = auto()


@dataclass(slots=True)
class ThreadResult:
    """Unified result data from transcription thread."""

    state: ThreadState
    text: str = ""
    duration_ms: int = 0  # Raw audio duration (human cognitive time)
    speech_duration_ms: int = 0  # Effective speech duration after VAD
    error_message: str = ""


class ResultThread(QThread):
    """
    QThread for audio recording and transcription.

    Pipeline: capture audio → VAD filtering → Whisper transcription → emit result.
    Signals cross thread boundaries safely via Qt's meta-object system.

    Emits unified resultReady signal with ThreadResult containing state, text, duration, and errors.
    Emits audioLevelUpdated signal with normalized amplitude for waveform visualization.
    """

    resultReady = pyqtSignal(ThreadResult)
    audioLevelUpdated = pyqtSignal(float)  # For waveform visualization

    def __init__(self, local_model: "WhisperModel | None" = None) -> None:
        """Initialize the ResultThread."""
        super().__init__()
        self.local_model = local_model
        self.is_recording: bool = False
        self.is_running: bool = True
        self.sample_rate: int | None = None
        self.mutex = QMutex()
        self.audio_service = AudioService(on_level_update=self.audioLevelUpdated.emit)

    def stop_recording(self) -> None:
        """Stop the current recording session."""
        self.mutex.lock()
        self.is_recording = False
        self.mutex.unlock()

    def stop(self) -> None:
        """Stop the entire thread execution."""
        self.mutex.lock()
        self.is_running = False
        self.mutex.unlock()
        self.resultReady.emit(ThreadResult(state=ThreadState.IDLE))
        self.wait()

    def run(self) -> None:
        """
        Main thread execution: record audio, transcribe, emit result.

        Always use start() to spawn thread - never call run() directly.
        Wrapped in try/finally to ensure cleanup on error.
        """
        try:
            if not self.is_running:
                return

            # Validate microphone before starting
            is_valid, error_msg = AudioService.validate_microphone()
            if not is_valid:
                logger.error(f"Microphone validation failed: {error_msg}")
                self.resultReady.emit(
                    ThreadResult(state=ThreadState.ERROR, error_message=error_msg)
                )
                return

            self.mutex.lock()
            self.is_recording = True
            self.mutex.unlock()

            self.resultReady.emit(ThreadResult(state=ThreadState.RECORDING))
            ConfigManager.console_print("Recording...")
            audio_data = self.audio_service.record_audio(
                should_stop=lambda: not (self.is_running and self.is_recording)
            )
            # Sync sample rate for duration calculation
            self.sample_rate = self.audio_service.sample_rate

            if not self.is_running:
                return

            if audio_data is None or len(audio_data) == 0:
                logger.warning(
                    "No audio data captured - recording was empty or too short"
                )
                self.resultReady.emit(
                    ThreadResult(
                        state=ThreadState.ERROR,
                        error_message="No audio captured. Please check your microphone.",
                    )
                )
                return

            self.resultReady.emit(ThreadResult(state=ThreadState.TRANSCRIBING))
            ConfigManager.console_print("Transcribing...")

            # Time the transcription process
            start_time = time.perf_counter()

            # Run transcription (this is the CPU/GPU intensive part)
            try:
                result, speech_duration_ms = transcribe(audio_data, self.local_model)
            except Exception as e:
                logger.error(f"Transcription failed: {e}")
                self.resultReady.emit(
                    ThreadResult(
                        state=ThreadState.ERROR,
                        error_message=f"Transcription failed: {e}",
                    )
                )
                return

            elapsed = time.perf_counter() - start_time

            ConfigManager.console_print(
                f"Transcription completed in {elapsed:.2f}s: {result}"
            )

            if not self.is_running:
                return

            # Raw audio duration (human cognitive time with pauses)
            duration_ms = (
                int(len(audio_data) / self.sample_rate * 1000)
                if self.sample_rate
                else 0
            )

            self.resultReady.emit(
                ThreadResult(
                    state=ThreadState.COMPLETE,
                    text=result,
                    duration_ms=duration_ms,
                    speech_duration_ms=speech_duration_ms,
                )
            )

        except Exception:
            logger.exception("Error during recording/transcription")
            self.resultReady.emit(ThreadResult(state=ThreadState.ERROR))
        finally:
            self.mutex.lock()
            self.is_recording = False
            self.mutex.unlock()

