"""
Voice Calibration - Analyze user's voice to optimize visualizer frequency bands.

Records speech samples, analyzes frequency distribution, and customizes
spectrum binning to center on the user's actual vocal range.
"""

from __future__ import annotations

import logging
from typing import Callable

import numpy as np
import sounddevice as sd

from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class VoiceCalibrator:
    """Calibrate visualizer to user's voice characteristics."""

    def __init__(self) -> None:
        self.sample_rate = 16000
        self.duration = 15  # seconds
        self.fft_size = 512
        self._cancel_requested = False
        self._stream = None

    def request_cancel(self) -> None:
        """Request calibration to stop (will stop current recording)."""
        self._cancel_requested = True
        # Stop the audio stream if it's running
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        self._cancel_requested = False
        self._stream = None

    def calibrate(
        self, on_progress: Callable[[str], None] | None = None
    ) -> dict[str, float]:
        """
        Record voice sample and analyze frequency distribution.

        Args:
            on_progress: Optional callback for status updates

        Returns:
            Dict with calibration results:
            - fundamental_freq: Dominant low frequency (fundamental pitch)
            - peak_freq: Frequency with most energy
            - freq_mean: Weighted mean of frequency energy
            - freq_std: Standard deviation of frequency distribution
            - energy_95th: 95th percentile frequency (where energy drops off)
        """
        if on_progress:
            on_progress(f"Recording {self.duration} seconds of your voice...")

        # Record audio using streaming to support cancellation
        logger.info(f"Recording voice sample for {self.duration}s...")
        audio_frames = []
        frames_needed = int(self.duration * self.sample_rate)
        frames_recorded = 0

        def audio_callback(indata, frames, time_info, status):
            nonlocal frames_recorded
            if status:
                logger.warning(f"Audio stream status: {status}")
            if not self._cancel_requested:
                audio_frames.append(indata.copy())
                frames_recorded += len(indata)

        # Start recording stream
        try:
            self._stream = sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                callback=audio_callback,
                blocksize=2048,
                dtype=np.float32,
            )
            if self._stream:
                self._stream.start()

                # Wait for recording to complete or be cancelled
                while frames_recorded < frames_needed and not self._cancel_requested:
                    sd.sleep(100)  # Check every 100ms

                self._stream.stop()
                self._stream.close()
            self._stream = None
        except Exception as e:
            logger.error(f"Error during recording: {e}")
            if self._stream:
                try:
                    self._stream.close()
                except Exception:
                    pass
            self._stream = None
            raise

        # If cancelled, return empty results
        if self._cancel_requested:
            raise ValueError("Calibration cancelled by user")

        # Concatenate audio frames
        audio = np.concatenate(audio_frames, axis=0).flatten()

        if on_progress:
            on_progress("Analyzing frequency distribution...")

        # Analyze in chunks to get distribution
        chunk_size = self.fft_size
        hop_size = chunk_size // 2

        # Accumulate frequency energy across all chunks
        freq_energy = np.zeros(self.fft_size // 2 + 1)
        num_chunks = 0

        hann_window = np.hanning(self.fft_size)

        for i in range(0, len(audio) - chunk_size, hop_size):
            chunk = audio[i : i + chunk_size]

            # Skip silent chunks
            rms = np.sqrt(np.mean(chunk**2))
            if rms < 0.01:  # Silence threshold
                continue

            # Compute FFT
            windowed = chunk * hann_window
            magnitudes = np.abs(np.fft.rfft(windowed))

            # Accumulate energy
            freq_energy += magnitudes
            num_chunks += 1

        if num_chunks == 0:
            raise ValueError("No speech detected - please speak during calibration")

        # Average energy across chunks
        freq_energy /= num_chunks

        # Convert bin indices to frequencies
        freqs = np.fft.rfftfreq(self.fft_size, 1 / self.sample_rate)

        # Find fundamental (low frequency peak, typically 85-300Hz for speech)
        low_freq_mask = (freqs >= 70) & (freqs <= 400)
        low_freq_bins = np.where(low_freq_mask)[0]
        fundamental_idx = low_freq_bins[np.argmax(freq_energy[low_freq_bins])]
        fundamental_freq = freqs[fundamental_idx]

        # Find overall peak frequency
        peak_idx = np.argmax(freq_energy)
        peak_freq = freqs[peak_idx]

        # Calculate weighted mean and std of frequency distribution
        # Weight each frequency by its energy
        total_energy = np.sum(freq_energy)
        freq_mean = np.sum(freqs * freq_energy) / total_energy
        freq_variance = np.sum(((freqs - freq_mean) ** 2) * freq_energy) / total_energy
        freq_std = np.sqrt(freq_variance)

        # Find 95th percentile (where energy concentration ends)
        cumulative_energy = np.cumsum(freq_energy)
        cumulative_energy /= cumulative_energy[-1]
        percentile_95_idx = np.searchsorted(cumulative_energy, 0.95)
        energy_95th = freqs[percentile_95_idx]

        results = {
            "fundamental_freq": float(fundamental_freq),
            "peak_freq": float(peak_freq),
            "freq_mean": float(freq_mean),
            "freq_std": float(freq_std),
            "energy_95th": float(energy_95th),
        }

        logger.info(f"Voice calibration results: {results}")

        if on_progress:
            on_progress(
                f"Calibration complete!\n"
                f"Fundamental: {fundamental_freq:.0f}Hz\n"
                f"Mean: {freq_mean:.0f}Hz\n"
                f"Range: {energy_95th:.0f}Hz"
            )

        return results

    def save_calibration(self, results: dict[str, float]) -> None:
        """Save calibration results to config."""
        # Save each calibration value
        for key, value in results.items():
            ConfigManager.set_config_value(value, "voice_calibration", key)

        # Save config to disk
        ConfigManager.save_config()
        logger.info("Voice calibration saved to config")

    def get_calibration(self) -> dict[str, float] | None:
        """Retrieve saved calibration from config."""
        return ConfigManager.get_config_section("voice_calibration")

    def compute_custom_bins(
        self, n_bins: int = 64, calibration: dict[str, float] | None = None
    ) -> np.ndarray:
        """
        Compute frequency bin edges optimized for user's voice.

        Args:
            n_bins: Number of frequency bands
            calibration: Voice calibration data (or use saved config)

        Returns:
            Array of bin edge indices for FFT magnitude array
        """
        if calibration is None:
            calibration = self.get_calibration()

        if calibration is None:
            # Fallback to generic logarithmic bins
            return self._default_bins(n_bins)

        # Use calibration to define FIXED frequency window (structure)
        fundamental = calibration.get("fundamental_freq", 85.0)
        energy_95 = calibration["energy_95th"]

        # Fixed bounds stay stable during rendering (no drift)
        # Shift lower bound to capture fundamental cleanly (start slightly below fundamental)
        min_freq = max(20.0, fundamental * 0.7)
        # Fixed upper bound based on 95th percentile, with headroom for harmonics
        max_freq = min(8000.0, energy_95 * 1.2)

        # Create logarithmic spacing across fixed range
        # This naturally emphasizes mids where formants live
        freq_edges = np.geomspace(min_freq, max_freq, n_bins + 1)

        # Convert frequencies to FFT bin indices
        fft_freqs = np.fft.rfftfreq(self.fft_size, 1 / self.sample_rate)
        bin_edges = np.searchsorted(fft_freqs, freq_edges)

        logger.info(
            f"Custom bins: {min_freq:.0f}Hz - {max_freq:.0f}Hz "
            f"(Fundamental: {fundamental:.0f}Hz)"
        )

        return bin_edges

    def _default_bins(self, n_bins: int) -> np.ndarray:
        """Default logarithmic bins (generic, not personalized)."""
        fft_freqs = np.fft.rfftfreq(self.fft_size, 1 / self.sample_rate)
        freq_min, freq_max = 60, 8000
        freq_edges = np.geomspace(freq_min, freq_max, n_bins + 1)
        return np.searchsorted(fft_freqs, freq_edges)
