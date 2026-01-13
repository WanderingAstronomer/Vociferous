"""
Audio capture and VAD service.

Handles microphone interaction, audio buffering, and Voice Activity Detection (VAD).
"""

import logging
from queue import Empty, Queue
from typing import Callable

import numpy as np
import sounddevice as sd
import webrtcvad
from numpy.typing import NDArray

from ui.constants import Timing
from utils import ConfigManager

logger = logging.getLogger(__name__)


class AudioService:
    """Service for capturing audio from the microphone with VAD."""

    def __init__(self, on_level_update: Callable[[float], None] | None = None) -> None:
        """
        Initialize the AudioService.

        Args:
            on_level_update: Optional callback for audio level updates (normalized 0-1).
        """
        self.on_level_update = on_level_update
        self.sample_rate = 16000

    @staticmethod
    def validate_microphone() -> tuple[bool, str]:
        """
        Validate that a working microphone is available.

        Returns:
            tuple[bool, str]: (is_valid, error_message)
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

    def record_audio(
        self, should_stop: Callable[[], bool]
    ) -> NDArray[np.int16] | None:
        """
        Record audio until silence is detected or should_stop() returns True.

        Args:
            should_stop: Callback that returns True if recording should stop manually.

        Returns:
            Recorded audio data or None if too short/failed.
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
                if self.on_level_update:
                    # int16 range is -32768 to 32767, normalize to 0-1
                    rms = np.sqrt(np.mean(frame_data.astype(np.float32) ** 2))
                    # Normalize: boosted sensitivity (lower divisor = bigger bars)
                    normalized = min(1.0, rms / 1500.0)
                    self.on_level_update(normalized)
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
            while not should_stop():
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
