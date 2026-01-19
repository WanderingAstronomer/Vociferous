"""
Core Application Constants.

Configuration values for audio, timing, and system limits that do not depend on UI.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioConfig:
    """Audio recording and processing constants."""

    DEFAULT_SAMPLE_RATE = 16000  # Hz - Whisper optimal sample rate
    CHANNELS = 1  # Mono audio
    INT16_SCALE = 32768.0  # 2^15 - int16 to float32 normalization factor


class FlowTiming:
    """
    Timing constants for core logic flows.
    """

    # Audio recording (seconds)
    HOTKEY_SOUND_SKIP = 0.15  # Skip initial audio to avoid key press (150ms)

    # Polling intervals (seconds)
    EVENT_LOOP_POLL = 0.1  # Input listener polling interval (100ms)
    AUDIO_QUEUE_TIMEOUT = 0.1  # Audio queue polling timeout (100ms)

    # Process management
    PROCESS_SHUTDOWN = 0.5  # Process graceful termination
    THREAD_SHUTDOWN_MS = 2000  # Stop timeout

    # Simulation
    KEYSTROKE_DELAY = 0.02
