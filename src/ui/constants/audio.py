"""
Audio configuration constants.

Sample rates, channels, and processing parameters.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AudioConfig:
    """Audio recording and processing constants."""

    DEFAULT_SAMPLE_RATE = 16000  # Hz - Whisper optimal sample rate
    CHANNELS = 1  # Mono audio
    INT16_SCALE = 32768.0  # 2^15 - int16 to float32 normalization factor
