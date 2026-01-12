"""
Audio recording and transcription thread for Vociferous.

Captures audio from microphone, applies Voice Activity Detection (VAD),
and sends audio to the Whisper transcription engine via QThread.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum, auto
from queue import Empty, Queue
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd
import webrtcvad
from numpy.typing import NDArray
from PyQt6.QtCore import QMutex, QThread, pyqtSignal

from transcription import transcribe
from ui.constants import Timing
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


def validate_microphone() -> tuple[bool, str]:
    """
    Validate that a working microphone is available.

    Returns:
        tuple[bool, str]: (is_valid, error_message)
            is_valid: True if a microphone is detected and accessible
            error_message: Empty string if valid, otherwise describes the issue
    """
    try:
        devices = sd.query_devices()
        if not devices:
            return False, "No audio devices detected"

        # Check for input devices
        input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
        if not input_devices:
            return (
                False,
                "No microphone detected. Please connect a microphone and try again.",
            )

        # Try to get default input device
        try:
            default_input = sd.query_devices(kind="input")
            if default_input is None:
                return False, "No default microphone configured"
        except Exception as e:
            return False, f"Cannot access microphone: {e}"

        return True, ""

    except Exception as e:
        logger.error(f"Microphone validation failed: {e}")
        return False, f"Audio system error: {e}"


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
            is_valid, error_msg = validate_microphone()
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
            audio_data = self._record_audio()

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

    def _record_audio(self) -> NDArray[np.int16] | None:
        """
        Record audio from microphone with Voice Activity Detection.

        Skips first 150ms to avoid hotkey press sounds.
        Uses WebRTC VAD to auto-stop when silence is detected.
        Returns None if recording is too short.
        """
        recording_options = ConfigManager.get_config_section("recording_options")
        self.sample_rate = recording_options.get("sample_rate") or 16000
        frame_duration_ms = 30  # WebRTC VAD frame duration
        frame_size = int(self.sample_rate * (frame_duration_ms / 1000.0))
        silence_duration_ms = recording_options.get("silence_duration") or 900
        silence_frames = int(silence_duration_ms / frame_duration_ms)

        # Skip initial audio to avoid capturing key press sounds
        initial_frames_to_skip = int(
            Timing.HOTKEY_SOUND_SKIP * self.sample_rate / frame_size
        )

        # Create VAD for voice activity detection modes
        recording_mode = recording_options.get("recording_mode") or "continuous"
        vad = None
        speech_detected = False
        silent_frame_count = 0

        if recording_mode in ("voice_activity_detection", "continuous"):
            vad = webrtcvad.Vad(2)  # Aggressiveness: 0-3 (higher = more aggressive)

        # Thread-safe queue for audio callback data
        audio_queue: Queue[NDArray[np.int16]] = Queue()
        recording: list[np.int16] = []

        def audio_callback(indata, frames, time_info, status) -> None:
            try:
                if status:
                    logger.debug(f"Audio callback status: {status}")
                # Copy audio data - numpy arrays share memory
                frame_data = indata[:, 0].copy()
                audio_queue.put(frame_data)

                # Calculate RMS amplitude for waveform visualization
                # int16 range is -32768 to 32767, normalize to 0-1
                rms = np.sqrt(np.mean(frame_data.astype(np.float32) ** 2))
                # Normalize: boosted sensitivity for better visualization (lower divisor = bigger bars)
                normalized = min(1.0, rms / 1500.0)
                self.audioLevelUpdated.emit(normalized)
            except Exception:
                logger.exception("Error in audio callback")

        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=frame_size,
                callback=audio_callback,
            )
        except Exception as e:
            logger.error(f"Failed to open audio stream: {e}")
            ConfigManager.console_print(f"Microphone error: {e}")
            return None

        with stream:
            while self.is_running and self.is_recording:
                try:
                    frame = audio_queue.get(timeout=Timing.AUDIO_QUEUE_TIMEOUT)
                except Empty:
                    continue

                if len(frame) < frame_size:
                    continue

                # Skip initial frames to avoid key press sounds
                if initial_frames_to_skip > 0:
                    initial_frames_to_skip -= 1
                    continue

                recording.extend(frame)

                if vad:
                    is_speech = vad.is_speech(frame.tobytes(), self.sample_rate)
                    match (is_speech, speech_detected):
                        case (True, False):
                            ConfigManager.console_print("Speech detected.")
                            speech_detected = True
                            silent_frame_count = 0
                        case (True, True):
                            silent_frame_count = 0
                        case (False, _):
                            silent_frame_count += 1

                    if speech_detected and silent_frame_count > silence_frames:
                        break

        audio_data = np.array(recording, dtype=np.int16)
        duration = len(audio_data) / self.sample_rate
        min_duration_ms = recording_options.get("min_duration") or 100

        ConfigManager.console_print(
            f"Recording finished: {audio_data.size} samples, {duration:.2f}s"
        )

        if (duration * 1000) < min_duration_ms:
            ConfigManager.console_print("Discarded: too short")
            return None

        return audio_data
