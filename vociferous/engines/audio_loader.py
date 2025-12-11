"""Shared audio loading utilities for engine implementations."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

PCM16_SCALE = 32768.0  # Normalization scale for 16-bit PCM audio


def load_audio_file(audio_path: Path) -> np.ndarray:
    """Load 16kHz mono PCM WAV file as normalized float32 numpy array."""
    with wave.open(str(audio_path), "rb") as wf:
        if wf.getnchannels() != 1:
            raise ValueError(f"Expected mono audio, got {wf.getnchannels()} channels")
        if wf.getsampwidth() != 2:
            raise ValueError(f"Expected 16-bit audio, got {wf.getsampwidth() * 8}-bit")
        if wf.getframerate() != 16000:
            raise ValueError(f"Expected 16kHz audio, got {wf.getframerate()}Hz")

        frames = wf.readframes(wf.getnframes())

    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / PCM16_SCALE
