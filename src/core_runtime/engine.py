"""
Core Application Engine.

Orchestrates the Audio -> Transcription pipeline without Qt dependencies.
"""

import logging
import time
from typing import Callable, Optional, TYPE_CHECKING

from src.services.audio_service import AudioService
from src.services.transcription_service import transcribe
from src.core.exceptions import VociferousError
from src.core_runtime.types import EngineState, TranscriptionResult

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class TranscriptionEngine:
    """
    Headless orchestration logic for recording and transcribing.
    """

    def __init__(
        self,
        local_model: "WhisperModel | None",
        on_result: Callable[[TranscriptionResult], None],
        on_audio_level: Optional[Callable[[float], None]] = None,
        on_spectrum_update: Optional[Callable[[list], None]] = None,
    ) -> None:
        self.local_model = local_model
        self.on_result = on_result
        self.is_recording = False
        self.is_running = True
        self.sample_rate: int | None = None

        # Audio Service setup
        # Note: AudioService might need to be passed in or factory created to allow easier mocking?
        # For now, instantiating it here is consistent with previous design.
        # But for headless harness, we might want to inject a mock AudioService.
        # Let's support injection or internal creation.

        self.audio_service = AudioService(
            on_level_update=on_audio_level, on_spectrum_update=on_spectrum_update
        )

    def stop_recording(self) -> None:
        """Signal recording loop to stop."""
        self.is_recording = False

    def stop(self) -> None:
        """Stop engine completely."""
        self.is_running = False
        self.is_recording = False  # Ensure recording stops too
        # In a real threaded loop, we might need synchronization primitives if this is called from another thread.
        # However, this class is just the logic. The caller handles threading.
        # Typically run_pipeline block until done.

    def run_pipeline(self) -> None:
        """
        Execute one recording -> transcription cycle.
        Blocking call (should be run in a thread).
        """
        try:
            if not self.is_running:
                return

            # 1. Validation
            is_valid, error_msg = AudioService.validate_microphone()
            if not is_valid:
                logger.error(f"Microphone validation failed: {error_msg}")
                self.on_result(
                    TranscriptionResult(
                        state=EngineState.ERROR, error_message=error_msg
                    )
                )
                return

            self.is_recording = True
            self.on_result(TranscriptionResult(state=EngineState.RECORDING))

            logger.info("Recording...")

            # 2. Recording Loop
            # This blocks until self.is_recording becomes False (via callback)
            # or until silence detection (if configured in AudioService)
            audio_data = self.audio_service.record_audio(
                should_stop=lambda: not (self.is_running and self.is_recording)
            )
            self.sample_rate = self.audio_service.sample_rate

            if not self.is_running:
                return

            # 3. Validation Post-Recording
            if audio_data is None or len(audio_data) == 0:
                logger.warning("No audio data captured.")
                self.on_result(
                    TranscriptionResult(
                        state=EngineState.ERROR,
                        error_message="No audio captured. Please check your microphone.",
                    )
                )
                return

            # 4. Transcription
            self.on_result(TranscriptionResult(state=EngineState.TRANSCRIBING))
            logger.info("Transcribing...")

            start_time = time.perf_counter()

            try:
                result, speech_duration_ms = transcribe(audio_data, self.local_model)
            except VociferousError as e:
                logger.error(f"Transcription error: {str(e)}", exc_info=True)
                msg = str(e)
                if e.doc_ref:
                    msg += f"\nSee: {e.doc_ref}"
                self.on_result(
                    TranscriptionResult(state=EngineState.ERROR, error_message=msg)
                )
                return
            except Exception as e:
                logger.exception(f"Unexpected transcription failure: {e}")
                self.on_result(
                    TranscriptionResult(
                        state=EngineState.ERROR,
                        error_message=f"Transcription failed: {e}",
                    )
                )
                return

            elapsed = time.perf_counter() - start_time
            logger.info(f"Transcription completed in {elapsed:.2f}s")

            if not self.is_running:
                return

            # 5. Success
            duration_ms = (
                int(len(audio_data) / self.sample_rate * 1000)
                if self.sample_rate
                else 0
            )

            self.on_result(
                TranscriptionResult(
                    state=EngineState.COMPLETE,
                    text=result,
                    duration_ms=duration_ms,
                    speech_duration_ms=speech_duration_ms,
                )
            )

        except Exception as e:
            logger.exception("Critical error in engine pipeline")
            self.on_result(
                TranscriptionResult(
                    state=EngineState.ERROR, error_message=f"System Error: {str(e)}"
                )
            )
        finally:
            self.is_recording = False
