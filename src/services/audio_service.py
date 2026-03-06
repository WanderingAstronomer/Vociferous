"""
Audio capture service.

Handles microphone interaction, audio buffering, and real-time spectrum
analysis for the visualizer.

FFT computation runs on a dedicated spectrum thread — never on the
PortAudio C callback thread.  The callback does only: copy frame,
enqueue for the recording loop, compute cheap RMS for the level meter,
and enqueue float data for the spectrum thread.
"""

import logging
import threading
import time
from queue import Empty, Queue
from typing import Callable, List

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray

from src.core.constants import FlowTiming
from src.core.exceptions import AudioError
from src.core.settings import VociferousSettings

logger = logging.getLogger(__name__)


class AudioService:
    """Service for capturing audio from the microphone.

    Spectrum analysis runs on a dedicated background thread that drains a
    small queue fed by the PortAudio callback.  This keeps the C-level
    audio callback fast and deterministic (copy + RMS only).

    Frequency bins are a fixed log distribution across the speech band
    (100–3400 Hz).  This replaces the deleted VoiceCalibrator — every adult
    human speaks in roughly the same frequency range, so per-user
    calibration was pure ceremony.
    """

    # Fixed speech-optimized frequency bin parameters.
    _FFT_WINDOW_SIZE: int = 512
    _FFT_BUFFER_SIZE: int = 1024
    _N_BINS: int = 64
    _SPEECH_FREQ_MIN: float = 100.0  # Hz — bottom of speech fundamental range
    _SPEECH_FREQ_MAX: float = 3400.0  # Hz — telephone band upper limit
    _FFT_INTERVAL: float = 0.033  # ~30 Hz spectrum update rate

    def __init__(
        self,
        settings_provider: Callable[[], VociferousSettings],
        on_level_update: Callable[[float], None] | None = None,
        on_spectrum_update: Callable[[List[float]], None] | None = None,
    ) -> None:
        """
        Initialize the AudioService.

        Args:
            settings_provider: Callable that returns the current application settings.
            on_level_update: Optional callback for audio level updates (normalized 0-1).
            on_spectrum_update: Optional callback for FFT spectrum (list of 64 floats).
        """
        self._settings_provider = settings_provider
        self.on_level_update = on_level_update
        self.on_spectrum_update = on_spectrum_update
        self.sample_rate = 16000

        # Pre-calculate fixed speech-optimized frequency bins.
        self._bin_edges = self._compute_speech_bins()

    # ------------------------------------------------------------------
    # Frequency bin calculation
    # ------------------------------------------------------------------

    def _compute_speech_bins(self) -> NDArray[np.intp]:
        """Fixed log-spaced frequency bins across the speech band.

        512-point FFT at 16 kHz → 257 real bins.  We map 64 display bands
        logarithmically across 100–3400 Hz — the telephone speech band that
        covers fundamentals through ~10th harmonic for all adult voices.
        No per-user calibration needed.
        """
        fft_freqs = np.fft.rfftfreq(self._FFT_WINDOW_SIZE, 1.0 / self.sample_rate)
        freq_edges = np.geomspace(
            self._SPEECH_FREQ_MIN,
            self._SPEECH_FREQ_MAX,
            self._N_BINS + 1,
        )
        return np.searchsorted(fft_freqs, freq_edges)

    # ------------------------------------------------------------------
    # Microphone validation
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Spectrum worker (dedicated thread — off the PortAudio callback)
    # ------------------------------------------------------------------

    def _spectrum_worker(
        self,
        spectrum_queue: "Queue[NDArray[np.float32]]",
        stop_event: threading.Event,
        hann_window: NDArray[np.float64],
    ) -> None:
        """Drain float frames from the queue, compute FFT, emit spectrum.

        Runs at ~30 Hz regardless of how fast the callback pushes frames.
        All numpy/FFT work happens here — never in the C callback.
        """
        fft_buffer = np.zeros(self._FFT_BUFFER_SIZE, dtype=np.float32)
        last_fft_time = 0.0

        while not stop_event.is_set():
            # Drain queue — keep only the latest frame for buffer update.
            latest: NDArray[np.float32] | None = None
            try:
                while True:
                    latest = spectrum_queue.get_nowait()
            except Empty:
                pass

            if latest is None:
                stop_event.wait(0.01)
                continue

            # Rate limit to ~30 Hz
            now = time.monotonic()
            if (now - last_fft_time) < self._FFT_INTERVAL:
                continue
            last_fft_time = now

            # Rolling buffer update
            n = len(latest)
            fft_buffer = np.roll(fft_buffer, -n)
            fft_buffer[-n:] = latest

            # Windowed FFT
            fft_slice = fft_buffer[-self._FFT_WINDOW_SIZE :] * hann_window
            magnitudes = np.abs(np.fft.rfft(fft_slice))

            # Logarithmic binning to 64 speech-optimized bands
            spectrum = np.zeros(self._N_BINS)
            for i in range(self._N_BINS):
                lo = int(self._bin_edges[i])
                hi = int(self._bin_edges[i + 1])
                if lo < hi:
                    spectrum[i] = np.mean(magnitudes[lo:hi])
                elif lo < len(magnitudes):
                    spectrum[i] = magnitudes[lo]

            # Spectral tilt compensation (~-6 dB/octave natural speech roll-off)
            tilt = np.linspace(1.0, 3.0, self._N_BINS)
            spectrum *= tilt

            # Frequency-selective noise gating
            base_gate = np.linspace(0.65, 0.35, self._N_BINS)
            gate_boost = self._settings_provider().visualizer.gate_aggression
            gated = np.maximum(0, spectrum - (base_gate + gate_boost))

            # Log scaling for perceptual dynamics
            result = np.log10(1 + gated * 95.0) / 1.9
            result_list = np.clip(result, 0.0, 1.0).tolist()

            try:
                if self.on_spectrum_update:
                    self.on_spectrum_update(result_list)
            except Exception:
                pass  # UI callback errors during shutdown

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_audio(self, should_stop: Callable[[], bool]) -> NDArray[np.int16] | None:
        """
        Record audio until should_stop() returns True.

        Args:
            should_stop: Callback that returns True when recording should stop.

        Returns:
            Recorded audio data or None if too short/failed.
        """
        s = self._settings_provider()
        self.sample_rate = s.recording.sample_rate
        frame_duration_ms = 30  # Frame size in ms for audio processing
        frame_size = int(self.sample_rate * (frame_duration_ms / 1000.0))
        # Skip initial audio to avoid capturing key press sounds
        initial_frames_to_skip = int(FlowTiming.HOTKEY_SOUND_SKIP * self.sample_rate / frame_size)
        max_recording_samples = int(s.recording.max_recording_minutes * 60 * self.sample_rate)

        # Thread-safe queue for audio callback data
        audio_queue: Queue[NDArray[np.int16]] = Queue()
        recording: list[np.int16] = []

        # ── Spectrum thread plumbing ──
        # Only spin up the thread if a spectrum callback is registered.
        spectrum_queue: Queue[NDArray[np.float32]] | None = None
        spectrum_stop = threading.Event()
        spectrum_thread: threading.Thread | None = None

        if self.on_spectrum_update:
            spectrum_queue = Queue(maxsize=64)
            hann_window = np.hanning(self._FFT_WINDOW_SIZE)
            # Recalculate bins in case sample_rate changed since __init__
            self._bin_edges = self._compute_speech_bins()
            spectrum_thread = threading.Thread(
                target=self._spectrum_worker,
                args=(spectrum_queue, spectrum_stop, hann_window),
                daemon=True,
                name="spectrum",
            )
            spectrum_thread.start()

        def audio_callback(indata, frames, time_info, status) -> None:
            """PortAudio C callback — kept minimal: copy, enqueue, RMS only."""
            try:
                if status:
                    logger.debug(f"Audio callback status: {status}")

                # Copy audio data — numpy arrays share memory with PortAudio
                frame_data = indata[:, 0].copy()
                audio_queue.put(frame_data, block=False)

                # Float conversion — reused for both RMS and spectrum enqueue
                float_data = frame_data.astype(np.float32) / 32768.0

                # Cheap RMS for the level meter (3 numpy ops, stays on callback)
                if self.on_level_update:
                    rms = np.sqrt(np.mean(float_data**2))
                    # Normalize based on measured loudness profile:
                    # Avg RMS: 0.054484, Max RMS: 0.377443
                    # Map 0.054 -> ~0.3-0.4 (visual baseline)
                    # Map 0.377 -> ~0.95 (near max)
                    normalized = min(1.0, (rms / 0.4) ** 0.7)
                    try:
                        self.on_level_update(normalized)
                    except Exception:
                        pass  # Ignore UI update errors during shutdown

                # Enqueue for spectrum thread (non-blocking, drop if full)
                if spectrum_queue is not None:
                    try:
                        spectrum_queue.put_nowait(float_data)
                    except Exception:
                        pass  # Queue full — spectrum thread will catch up

            except Exception:
                # Don't let exceptions bubble up to C-layer (PortAudio)
                logger.debug("audio_callback error", exc_info=True)

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
            raise AudioError(f"Failed to open audio stream: {e}") from e

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

                    if len(recording) >= max_recording_samples:
                        logger.warning(
                            "Recording exceeded max duration (%.1f min) — stopping automatically",
                            s.recording.max_recording_minutes,
                        )
                        break
        except Exception as e:
            logger.error(f"Recording loop error: {e}")
            raise AudioError(f"Recording loop error: {e}") from e
        finally:
            # Stop the spectrum thread before draining — it's no longer needed.
            spectrum_stop.set()
            if spectrum_thread is not None:
                spectrum_thread.join(timeout=1.0)

            # Drain any remaining frames that were captured by the audio
            # callback but not yet consumed by the recording loop.  Without
            # this the final fraction of a second can be silently lost,
            # causing sentence truncation at the end of recordings.
            drained = 0
            while not audio_queue.empty():
                try:
                    frame = audio_queue.get_nowait()
                    if len(frame) >= frame_size:
                        recording.extend(frame)
                        drained += 1
                except Empty:
                    break
            if drained:
                logger.debug("Drained %d residual frames from audio queue", drained)

        audio_data = np.array(recording, dtype=np.int16)
        duration = len(audio_data) / self.sample_rate
        min_duration_ms = self._settings_provider().recording.min_duration_ms

        logger.info(f"Recording finished: {audio_data.size} samples, {duration:.2f}s")

        if (duration * 1000) < min_duration_ms:
            logger.warning("Discarded: too short")
            return None

        return audio_data
