"""
RecordingSession — owns the recording state machine and audio→transcribe→store pipeline.

Extracted from ApplicationCoordinator. Holds the ASR model reference so it
survives across recordings without reloading.
"""

from __future__ import annotations

import logging
import platform
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.core.settings import VociferousSettings
    from src.database.db import TranscriptDB
    from src.services.audio_cache import AudioCacheManager
    from src.services.audio_service import AudioService
    from src.services.audio_spool import AudioSpoolWriter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Clipboard helper (platform-native, no window focus required)
# ---------------------------------------------------------------------------


def _copy_to_system_clipboard(text: str) -> None:
    """Copy text to the system clipboard using platform-native CLI tools."""
    system = platform.system()
    try:
        if system == "Linux":
            for cmd in (
                ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"],
            ):
                try:
                    subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=3)
                    logger.debug("Copied %d chars to clipboard via %s", len(text), cmd[0])
                    return
                except FileNotFoundError:
                    continue
            logger.warning("No clipboard tool found (install xclip or xsel)")
        elif system == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True, timeout=3)
            logger.debug("Copied %d chars to clipboard via pbcopy", len(text))
        elif system == "Windows":
            subprocess.run(["clip.exe"], input=text.encode("utf-16le"), check=True, timeout=3)
            logger.debug("Copied %d chars to clipboard via clip.exe", len(text))
        else:
            logger.warning("Auto-copy not supported on %s", system)
    except Exception:
        logger.warning("Failed to copy to system clipboard", exc_info=True)


# ---------------------------------------------------------------------------
# RecordingSession
# ---------------------------------------------------------------------------


class RecordingSession:
    """
    Owns the recording state machine and the audio→transcribe→store pipeline.

    Constructed once during ApplicationCoordinator.start() and wired into
    the CommandBus via handle_begin / handle_stop / handle_cancel / handle_toggle.
    All providers are lambdas so they always resolve to the current live object.
    """

    def __init__(
        self,
        *,
        audio_service_provider: Callable[[], AudioService | None],
        settings_provider: Callable[[], VociferousSettings],
        db_provider: Callable[[], TranscriptDB | None],
        event_bus_emit: Callable,
        shutdown_event: threading.Event,
        insight_manager_provider: Callable[[], Any],
        motd_manager_provider: Callable[[], Any],
        title_generator_provider: Callable[[], Any] = lambda: None,
    ) -> None:
        self._audio_service_provider = audio_service_provider
        self._settings_provider = settings_provider
        self._db_provider = db_provider
        self._emit = event_bus_emit
        self._shutdown_event = shutdown_event
        self._insight_manager_provider = insight_manager_provider
        self._motd_manager_provider = motd_manager_provider
        self._title_generator_provider = title_generator_provider

        self._is_recording = False
        self._recording_lock = threading.Lock()
        self._recording_stop = threading.Event()
        self._recording_thread: threading.Thread | None = None
        self._asr_model: Any = None
        self._audio_pipeline: Any = None  # lazy AudioPipeline instance
        self._spool: AudioSpoolWriter | None = None
        self._audio_cache: AudioCacheManager | None = None

    # --- Public lifecycle interface ---

    @property
    def thread(self) -> threading.Thread | None:
        return self._recording_thread

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def audio_cache(self) -> AudioCacheManager | None:
        return self._audio_cache

    @audio_cache.setter
    def audio_cache(self, value: AudioCacheManager) -> None:
        self._audio_cache = value

    def load_asr_model(self) -> None:
        """Warm-load the Whisper model (faster-whisper/CTranslate2) and emit engine_status events."""
        settings = self._settings_provider()
        try:
            from src.services.transcription_service import create_local_model

            self._asr_model = create_local_model(settings)
            self._emit("engine_status", {"asr": "ready"})
        except Exception:
            logger.exception("ASR model failed to load (will retry on first transcription)")
            self._emit("engine_status", {"asr": "unavailable"})

    def load_vad_model(self) -> None:
        """Preload the Silero VAD ONNX model so first transcription has no cold-start."""
        try:
            from src.services.audio_pipeline import AudioPipeline

            if self._audio_pipeline is None:
                self._audio_pipeline = AudioPipeline()
            self._audio_pipeline._load_vad_model()
            logger.info("Silero VAD model preloaded")
        except Exception:
            logger.exception("VAD model preload failed (will retry on first transcription)")

    def unload_asr_model(self) -> None:
        """Release the ASR model (called during engine restart or cleanup)."""
        if self._asr_model:
            try:
                del self._asr_model
                self._asr_model = None
            except Exception:
                logger.exception("ASR model cleanup failed")

    def cancel_for_shutdown(self) -> None:
        """Signal the recording loop to abort without transcribing."""
        self._recording_stop.set()
        self._is_recording = False
        if self._spool is not None:
            self._spool.discard()
            self._spool = None

    # --- Intent handlers ---

    def handle_begin(self, intent: Any) -> None:
        with self._recording_lock:
            audio_service = self._audio_service_provider()
            if self._is_recording or not audio_service:
                return

            # Pre-check: is the ASR model file actually available?
            from src.core.model_registry import ASR_MODELS, get_asr_model
            from src.core.resource_manager import ResourceManager

            settings = self._settings_provider()
            model_id = settings.model.model
            asr_model = get_asr_model(model_id) or ASR_MODELS.get("large-v3-turbo-int8")
            if asr_model:
                local_dir_name = asr_model.repo.split("/")[-1]
                model_path = ResourceManager.get_user_cache_dir("models") / local_dir_name / asr_model.model_file
                if not model_path.exists():
                    self._emit(
                        "transcription_error",
                        {"message": "No ASR model downloaded. Go to Settings to download a speech recognition model."},
                    )
                    return

            self._is_recording = True

        self._recording_stop.clear()

        # Create disk spool for crash-resilient recording
        from src.services.audio_spool import AudioSpoolWriter

        session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        settings = self._settings_provider()
        self._spool = AudioSpoolWriter(session_id, sample_rate=settings.recording.sample_rate)

        self._emit("recording_started", {})

        t = threading.Thread(target=self._recording_loop, daemon=True, name="recording")
        self._recording_thread = t
        t.start()

    def handle_stop(self, intent: Any) -> None:
        if not self._is_recording:
            return
        self._recording_stop.set()

    def handle_cancel(self, intent: Any) -> None:
        if not self._is_recording:
            return
        self._recording_stop.set()
        self._is_recording = False
        if self._spool is not None:
            self._spool.discard()
            self._spool = None
        self._emit("recording_stopped", {"cancelled": True})

    def handle_toggle(self, intent: Any) -> None:
        if self._is_recording:
            self.handle_stop(intent)
        else:
            self.handle_begin(intent)

    def handle_import(self, intent: Any) -> None:
        """Import an audio file for transcription (runs decode+transcribe on a background thread)."""
        file_path: str = intent.file_path
        cleanup: bool = getattr(intent, "cleanup_source", False)
        if not file_path:
            self._emit("transcription_error", {"message": "No file path provided"})
            return

        path = Path(file_path)
        if not path.is_file():
            self._emit("transcription_error", {"message": f"File not found: {path.name}"})
            return

        display_name = path.stem  # filename without extension

        def _import_worker() -> None:
            try:
                import numpy as np
                from faster_whisper.audio import decode_audio

                # decode_audio returns float32 at target sample rate (uses ffmpeg)
                float_audio = decode_audio(str(path), sampling_rate=16000)

                # Convert to int16 for the standard AudioPipeline (VAD, normalization)
                int16_audio = (float_audio * 32768).clip(-32768, 32767).astype(np.int16)

                if len(int16_audio) == 0:
                    self._emit("transcription_error", {"message": "Audio file is empty"})
                    return

                self._transcribe_and_store(
                    int16_audio,
                    source_tag="Imported",
                    display_name=display_name,
                )
            except Exception as e:
                logger.exception("Audio file import failed: %s", path.name)
                self._emit("transcription_error", {"message": f"Import failed: {e}"})
            finally:
                if cleanup:
                    path.unlink(missing_ok=True)

        t = threading.Thread(target=_import_worker, daemon=True, name="audio-import")
        t.start()

    def handle_retranscribe(self, intent: Any) -> None:
        """Re-transcribe a transcript from its cached audio WAV."""
        transcript_id: int = intent.transcript_id
        if not transcript_id:
            self._emit("transcription_error", {"message": "No transcript ID provided"})
            return

        if self._audio_cache is None:
            self._emit("transcription_error", {"message": "Audio cache not available"})
            return

        wav_path = self._audio_cache.get_path(transcript_id)
        if wav_path is None:
            self._emit("transcription_error", {"message": "No cached audio for this transcript"})
            # Clear stale flag
            db = self._db_provider()
            if db:
                db.set_audio_cached(transcript_id, False)
                self._emit("transcript_updated", {"id": transcript_id})
            return

        def _retranscribe_worker() -> None:
            try:
                import numpy as np
                from faster_whisper.audio import decode_audio

                float_audio = decode_audio(str(wav_path), sampling_rate=16000)
                int16_audio = (float_audio * 32768).clip(-32768, 32767).astype(np.int16)

                if len(int16_audio) == 0:
                    self._emit("transcription_error", {"message": "Cached audio is empty"})
                    return

                from src.services.transcription_service import create_local_model, transcribe

                settings = self._settings_provider()

                if self._asr_model is None:
                    try:
                        self._asr_model = create_local_model(settings)
                    except Exception as model_err:
                        logger.error("ASR model failed to load: %s", model_err)
                        self._emit("transcription_error", {"message": "ASR model failed to load"})
                        return

                if self._audio_pipeline is None:
                    from src.services.audio_pipeline import AudioPipeline
                    self._audio_pipeline = AudioPipeline()

                text, speech_duration_ms, _transcription_time_ms = transcribe(
                    int16_audio,
                    settings=settings,
                    local_model=self._asr_model,
                    audio_pipeline=self._audio_pipeline,
                )

                if not text.strip():
                    self._emit("transcription_error", {"message": "No speech detected in cached audio"})
                    return

                db = self._db_provider()
                if db:
                    duration_ms = int(len(int16_audio) / 16000 * 1000)
                    db.update_normalized_text(transcript_id, text)
                    self._emit("transcript_updated", {"id": transcript_id})

                logger.info("Re-transcription complete for transcript %d: %d chars", transcript_id, len(text))

            except Exception as e:
                logger.exception("Re-transcription failed for transcript %d", transcript_id)
                self._emit("transcription_error", {"message": f"Re-transcription failed: {e}"})

        t = threading.Thread(target=_retranscribe_worker, daemon=True, name="retranscribe")
        t.start()

    # --- Pipeline ---

    def _recording_loop(self) -> None:
        """Background thread: record audio → transcribe → store → emit."""
        spool = self._spool
        spool_path: Path | None = None
        try:
            audio_service = self._audio_service_provider()
            audio_data = audio_service.record_audio(
                should_stop=lambda: self._recording_stop.is_set(),
                spool_writer=spool,
            )

            # Finalize spool regardless of cancel state
            if spool is not None:
                spool_path = spool.finalize()
                self._spool = None

            # Check if cancelled during recording
            if not self._is_recording:
                # Cancelled — spool already finalized (not discarded) for
                # crash-recovery.  handle_cancel discards it explicitly.
                return

            self._is_recording = False
            self._emit("recording_stopped", {"cancelled": False})

            if audio_data is None or len(audio_data) == 0:
                self._emit("transcription_error", {"message": "Recording too short or empty"})
                self._cleanup_spool(spool_path)
                return

            self._transcribe_and_store(audio_data, spool_path=spool_path)

        except Exception as e:
            logger.exception("Recording loop error")
            # Finalize spool on error so audio survives on disk
            if spool is not None and spool_path is None:
                try:
                    spool.finalize()
                except Exception:
                    pass
                self._spool = None
            self._is_recording = False
            self._emit("recording_stopped", {"cancelled": False})
            self._emit("transcription_error", {"message": str(e)})

    def _transcribe_and_store(
        self,
        audio_data: Any,
        *,
        spool_path: Path | None = None,
        source_tag: str | None = None,
        display_name: str | None = None,
    ) -> None:
        """Run transcription on audio data, store result, and emit events."""
        if self._shutdown_event.is_set():
            logger.debug("Transcription skipped — shutdown in progress")
            return

        from src.services.transcription_service import create_local_model, transcribe

        settings = self._settings_provider()
        try:
            # Lazy-load ASR model if warm load failed at startup
            if self._asr_model is None:
                logger.info("ASR model not loaded — attempting lazy recovery...")
                try:
                    self._asr_model = create_local_model(settings)
                except Exception as model_err:
                    logger.error("ASR model failed to load: %s", model_err)
                    self._emit("engine_status", {"asr": "unavailable"})
                    self._emit(
                        "transcription_error",
                        {
                            "message": "Speech recognition model failed to load. Check GPU memory or switch to a smaller model in Settings.",
                        },
                    )
                    return

            # Lazy-create the AudioPipeline (holds cached Silero VAD session)
            if self._audio_pipeline is None:
                from src.services.audio_pipeline import AudioPipeline

                self._audio_pipeline = AudioPipeline()

            text, speech_duration_ms, transcription_time_ms = transcribe(
                audio_data,
                settings=settings,
                local_model=self._asr_model,
                audio_pipeline=self._audio_pipeline,
            )

            if not text.strip():
                self._emit("transcription_error", {"message": "No speech detected"})
                self._cleanup_spool(spool_path)
                return

            # Store in database
            duration_ms = int(len(audio_data) / 16000 * 1000)
            transcript = None
            db = self._db_provider()
            if db:
                transcript = db.add_transcript(
                    raw_text=text,
                    duration_ms=duration_ms,
                    speech_duration_ms=speech_duration_ms,
                    transcription_time_ms=transcription_time_ms,
                    display_name=display_name,
                )
                if source_tag and transcript:
                    db.add_system_tag_to_transcript(transcript.id, source_tag)
                    if source_tag == "Imported" and settings.output.exclude_imported_from_analytics:
                        db.set_analytics_inclusion(transcript.id, False)

            self._emit(
                "transcription_complete",
                {
                    "text": text,
                    "id": transcript.id if transcript else None,
                    "duration_ms": duration_ms,
                    "speech_duration_ms": speech_duration_ms,
                },
            )

            # Schedule lazy insight generation if the cache is stale.
            insight_manager = self._insight_manager_provider()
            if insight_manager is not None:
                insight_manager.maybe_schedule()
            motd_manager = self._motd_manager_provider()
            if motd_manager is not None:
                motd_manager.maybe_schedule()

            # Schedule SLM-based auto-titling for the new transcript.
            # Skip initial title when auto-refine is enabled — refinement
            # completion will retitle with better text, avoiding double work.
            if not settings.output.auto_refine:
                title_gen = self._title_generator_provider()
                if title_gen is not None and transcript is not None:
                    title_gen.schedule(transcript.id, text)

            # When auto-refine is active, defer clipboard until refinement
            # completes — otherwise we'd paste raw text that's about to be rewritten.
            if settings.output.auto_copy_to_clipboard and not settings.output.auto_refine:
                _copy_to_system_clipboard(text)

            # Cache audio WAV for crash recovery / future re-transcription
            if spool_path is not None and transcript is not None and self._audio_cache is not None:
                try:
                    wav_path, evicted_ids = self._audio_cache.store(
                        transcript.id,
                        spool_path,
                        max_cache_minutes=settings.recording.audio_cache_minutes,
                    )
                    if wav_path is not None and db is not None:
                        db.set_audio_cached(transcript.id, True)
                    # Clear has_audio_cached for transcripts whose WAVs were pruned
                    if db is not None:
                        for evicted_id in evicted_ids:
                            db.set_audio_cached(evicted_id, False)
                except Exception:
                    logger.warning("Audio cache store failed", exc_info=True)
                    self._cleanup_spool(spool_path)
            else:
                self._cleanup_spool(spool_path)

            logger.info("Transcription complete: %d chars, %dms", len(text), duration_ms)

        except Exception as e:
            logger.exception("Transcription failed")
            self._cleanup_spool(spool_path)
            self._emit("transcription_error", {"message": str(e)})

    @staticmethod
    def _cleanup_spool(spool_path: Path | None) -> None:
        """Delete a spool file if it exists (cache disabled or error path)."""
        if spool_path is not None:
            try:
                spool_path.unlink(missing_ok=True)
            except OSError:
                pass
