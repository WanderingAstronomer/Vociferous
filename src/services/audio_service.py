"""
Audio capture and VAD service.

Handles microphone interaction, audio buffering, and Voice Activity Detection (VAD).
"""

import logging
import time
from queue import Empty, Queue
from typing import Callable, List

import numpy as np
import sounddevice as sd
import webrtcvad
from numpy.typing import NDArray

from src.core_runtime.constants import FlowTiming
from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class AudioService:
    """Service for capturing audio from the microphone with VAD."""

    def __init__(
        self,
        on_level_update: Callable[[float], None] | None = None,
        on_spectrum_update: Callable[[List[float]], None] | None = None,
    ) -> None:
        """
        Initialize the AudioService.

        Args:
            on_level_update: Optional callback for audio level updates (normalized 0-1).
            on_spectrum_update: Optional callback for FFT spectrum (list of 16 floats).
        """
        self.on_level_update = on_level_update
        self.on_spectrum_update = on_spectrum_update
        self.sample_rate = 16000

        # FFT State
        self._last_fft_time = 0.0
        self._fft_interval = 0.033  # ~30Hz update rate
        self._fft_buffer = np.zeros(1024, dtype=np.float32)  # Rolling buffer

        # Pre-calculate FFT logarithmic bins (default 64 bands for CAVA-like resolution)
        self._n_bins = 64
        self._calculate_bin_edges()

    def _calculate_bin_edges(self) -> None:
        """Calculate bin edges for logarithmic FFT grouping (with optional voice calibration)."""
        # Check if user has calibrated their voice
        calibration = ConfigManager.get_config_section("voice_calibration")

        if calibration and isinstance(calibration, dict):
            # Use personalized bins centered on user's voice
            from src.services.voice_calibration import VoiceCalibrator

            calibrator = VoiceCalibrator()
            self._bin_edges = calibrator.compute_custom_bins(self._n_bins, calibration)
            logger.info(
                f"Using voice-calibrated frequency bins "
                f"(fundamental: {calibration.get('fundamental_freq', 0):.0f}Hz)"
            )
        else:
            # Default logarithmic bins (generic)
            # 512-point FFT gives 257 real bins at 16kHz sample rate.
            # Start at bin 7 (~218 Hz) to filter out low-frequency rumble/hum
            min_bin = 7
            max_bin = 256  # Nyquist at 8kHz

            edges = [min_bin]
            for i in range(1, self._n_bins + 1):
                next_edge = max(
                    edges[-1] + 1,
                    int(min_bin * (max_bin / min_bin) ** (i / self._n_bins)),
                )
                edges.append(next_edge)
            self._bin_edges = np.array(edges)
            logger.info("Using default frequency bins (no voice calibration)")

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

    def record_audio(self, should_stop: Callable[[], bool]) -> NDArray[np.int16] | None:
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
            FlowTiming.HOTKEY_SOUND_SKIP * self.sample_rate / frame_size
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

        # Pre-allocate window for FFT
        fft_window_size = 512
        hann_window = np.hanning(fft_window_size)

        def audio_callback(indata, frames, time_info, status) -> None:
            try:
                if status:
                    logger.debug(f"Audio callback status: {status}")

                # Copy audio data - numpy arrays share memory
                frame_data = indata[:, 0].copy()

                # Check directly if we should still be running to avoid pushing to closed queue
                # We can't easily check the lambda here as it might block or be complex,
                # but we can rely on exception handling for the queue.
                audio_queue.put(frame_data, block=False)

                # Normalize float data for calculations
                float_data = frame_data.astype(np.float32) / 32768.0

                # Calculate RMS amplitude for waveform visualization
                if self.on_level_update:
                    rms = np.sqrt(np.mean(float_data**2))
                    # Normalize based on measured loudness profile:
                    # Avg RMS: 0.054484, Max RMS: 0.377443
                    # Map 0.054 -> ~0.3-0.4 (visual baseline)
                    # Map 0.377 -> ~0.95 (near max)
                    normalized = min(
                        1.0, (rms / 0.4) ** 0.7
                    )  # Gentle power curve for natural scaling
                    try:
                        self.on_level_update(normalized)
                    except Exception:
                        pass  # Ignore UI update errors during shutdown

                # Calculate FFT Spectrum (Rate Limited)
                current_time = time.time()
                if (
                    self.on_spectrum_update
                    and (current_time - self._last_fft_time) > self._fft_interval
                ):
                    self._last_fft_time = current_time

                    # Manual rolling buffer update
                    self._fft_buffer = np.roll(self._fft_buffer, -len(float_data))
                    self._fft_buffer[-len(float_data) :] = float_data

                    # Take latest slice
                    fft_slice = self._fft_buffer[-fft_window_size:] * hann_window

                    # Compute FFT
                    magnitudes = np.abs(np.fft.rfft(fft_slice))

                    # Logarithmic binning to 64 bands
                    spectrum = np.zeros(self._n_bins)
                    for i in range(self._n_bins):
                        start = self._bin_edges[i]
                        end = self._bin_edges[i + 1]
                        if start < end:
                            spectrum[i] = np.mean(magnitudes[start:end])
                        else:
                            spectrum[i] = (
                                magnitudes[start] if start < len(magnitudes) else 0
                            )

                    # Spectral tilt compensation (counteract natural roll-off)
                    # Speech has ~-6dB/octave natural decay
                    # Apply gentle boost to higher frequencies for perceptual balance
                    tilt_compensation = np.linspace(
                        1.0, 3.0, self._n_bins
                    )  # 3x boost at highest bin
                    spectrum *= tilt_compensation

                    # Frequency-selective noise gating (AFTER tilt compensation)
                    # Low frequencies (machine hum, fans, electrical noise) need aggressive gating
                    # High frequencies get less aggressive gating now that tilt is compensated
                    # Base gate gradient from aggressive to moderate
                    base_gate = np.linspace(0.65, 0.35, self._n_bins)

                    # User-configurable gate boost (0.0 to 0.5 additional suppression)
                    gate_boost = (
                        ConfigManager.get_config_value(
                            "bar_spectrum", "gate_aggression"
                        )
                        or 0.0
                    )
                    gate_curve = base_gate + gate_boost

                    # Apply frequency-dependent gating
                    gated_spectrum = np.maximum(0, spectrum - gate_curve)

                    # Logarithmic scaling calibrated to measured loudness profile:
                    # Avg speech (RMS 0.054) -> mid-range visualization (~0.4-0.6)
                    # Peak speech (RMS 0.377) -> high visualization (~0.85-0.95)
                    # Using log curve with tuned multiplier for natural dynamics
                    spectrum = np.log10(1 + gated_spectrum * 95.0) / 1.9
                    spectrum = np.clip(spectrum, 0.0, 1.0).tolist()

                    try:
                        self.on_spectrum_update(spectrum)
                    except Exception:
                        pass

            except Exception:
                # Don't let exceptions bubble up to C-layer (PortAudio)
                pass

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
            return None

        # Robust recording loop
        try:
            with stream:
                while not should_stop():
                    try:
                        frame = audio_queue.get(timeout=FlowTiming.AUDIO_QUEUE_TIMEOUT)
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
                                logger.debug("Speech detected.")
                                speech_detected = True
                                silent_frame_count = 0
                            case (True, True):
                                silent_frame_count = 0
                            case (False, _):
                                silent_frame_count += 1

                        if speech_detected and silent_frame_count > silence_frames:
                            break
        except Exception as e:
            logger.error(f"Recording loop error: {e}")
        finally:
            # Explicit cleanup if needed (stream context manager handles close)
            # We clear the queue to drop any pending frames and help gc
            while not audio_queue.empty():
                try:
                    audio_queue.get_nowait()
                except Empty:
                    break

        audio_data = np.array(recording, dtype=np.int16)
        duration = len(audio_data) / self.sample_rate
        min_duration_ms = recording_options.get("min_duration") or 100

        logger.info(f"Recording finished: {audio_data.size} samples, {duration:.2f}s")

        if (duration * 1000) < min_duration_ms:
            logger.warning("Discarded: too short")
            return None

        return audio_data
