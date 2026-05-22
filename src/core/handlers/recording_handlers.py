"""
RecordingSession — owns the recording state machine and audio→transcribe→store pipeline.

Extracted from ApplicationCoordinator. Holds the ASR model reference so it
survives across recordings without reloading.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from src.core.clipboard import copy_to_system_clipboard as _copy_to_system_clipboard
from src.core.command_bus import handles
from src.core.engine_status import normalize_engine_error
from src.core.intents.definitions import (
    BeginRecordingIntent,
    CancelRecordingIntent,
    DeleteRecoveredRecordingIntent,
    ImportAudioFileIntent,
    RetranscribeIntent,
    StopRecordingIntent,
    ToggleRecordingIntent,
    TranscribeRecoveredRecordingIntent,
)

if TYPE_CHECKING:
    from src.core.settings import VociferousSettings
    from src.database.db import TranscriptDB
    from src.services.audio_cache import AudioCacheManager
    from src.services.audio_service import AudioService
    from src.services.audio_vault import AudioVaultWriter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audio decode helper (shared between import + retranscribe paths)
# ---------------------------------------------------------------------------


def _decode_audio_file_to_int16(path: Path):
    """Decode an audio file to a 16kHz int16 numpy array via faster_whisper/ffmpeg.

    Returns the int16 array (may be empty — callers must check len()).
    """
    import numpy as np
    from faster_whisper.audio import decode_audio

    float_audio = decode_audio(str(path), sampling_rate=16000)
    return (float_audio * 32768).clip(-32768, 32767).astype(np.int16)


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
        title_generator_provider: Callable[[], Any] = lambda: None,
    ) -> None:
        self._audio_service_provider = audio_service_provider
        self._settings_provider = settings_provider
        self._db_provider = db_provider
        self._emit = event_bus_emit
        self._shutdown_event = shutdown_event
        self._insight_manager_provider = insight_manager_provider
        self._title_generator_provider = title_generator_provider

        self._is_recording = False
        self._recording_lock = threading.Lock()
        self._recording_stop = threading.Event()
        self._recording_thread: threading.Thread | None = None
        self._asr_model: Any = None
        self._asr_runtime_summary: dict[str, object] | None = None
        self.last_asr_error: str | None = None
        self.is_transcribing = False
        self._audio_pipeline: Any = None  # lazy AudioPipeline instance
        self._spool: AudioVaultWriter | None = None
        self._audio_cache: AudioCacheManager | None = None

    # --- Public lifecycle interface ---

    @property
    def thread(self) -> threading.Thread | None:
        return self._recording_thread

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def is_asr_loaded(self) -> bool:
        return self._asr_model is not None

    def get_asr_runtime_summary(self) -> dict[str, object] | None:
        return dict(self._asr_runtime_summary) if self._asr_runtime_summary else None

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
            self._asr_runtime_summary = getattr(self._asr_model, "_vociferous_runtime_summary", None)
            self.last_asr_error = None
            self._emit("engine_status", {"asr": "ready"})
        except Exception as e:
            logger.exception("ASR model failed to load (will retry on first transcription)")
            self.last_asr_error = normalize_engine_error(e)
            self._emit("engine_status", {"asr": "unavailable"})

    def load_vad_model(self) -> None:
        """Preload the Silero VAD ONNX model so first transcription has no cold-start."""
        try:
            from src.services.audio_pipeline import AudioPipeline

            if self._audio_pipeline is None:
                settings = self._settings_provider()
                self._audio_pipeline = AudioPipeline(sensitivity=settings.recording.vad_sensitivity)
            self._audio_pipeline._load_vad_model()
            logger.info("Silero VAD model preloaded")
        except Exception:
            logger.exception("VAD model preload failed (will retry on first transcription)")

    def unload_asr_model(self) -> None:
        """Release the ASR model (called during engine restart)."""
        import gc

        if self._asr_model is not None:
            logger.info("Unloading ASR model...")
            self._asr_model = None
            self._asr_runtime_summary = None
            gc.collect()

    def shutdown_models(self) -> None:
        """Mark models as released WITHOUT running native destructors.

        During process shutdown, forcing gc.collect() triggers CTranslate2's
        native CUDA destructor while the driver is tearing down → abort().
        Just null the tracking flag; the OS reclaims everything on exit.
        """
        self._asr_model = None
        self._asr_runtime_summary = None

    def cancel_for_shutdown(self) -> None:
        """Signal the recording loop to abort without transcribing."""
        self._recording_stop.set()
        self._is_recording = False

    # --- Intent handlers ---

    @handles(BeginRecordingIntent)
    def handle_begin(self, intent: Any) -> None:
        with self._recording_lock:
            audio_service = self._audio_service_provider()
            if self._is_recording or not audio_service:
                return

            # Pre-check: is the ASR model file actually available?
            from src.core.model_registry import ASR_MODELS, get_asr_model
            from src.core.resource_manager import ResourceManager

            settings = self._settings_provider()
            if settings.model.provider == "local_faster_whisper":
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

            # Pre-check: is a working microphone available?
            from src.services.audio_service import AudioService

            mic_ok, mic_err = AudioService.validate_microphone()
            if not mic_ok:
                self._emit("transcription_error", {"message": mic_err})
                return

            self._is_recording = True

        self._recording_stop.clear()

        db = self._db_provider()
        if db is None:
            with self._recording_lock:
                self._is_recording = False
            self._emit("transcription_error", {"message": "Database not available for durable recording"})
            return

        from src.services.audio_vault import AudioVaultError, AudioVaultWriter

        session_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        settings = self._settings_provider()
        try:
            self._spool = AudioVaultWriter(
                db=db,
                session_id=session_id,
                sample_rate=settings.recording.sample_rate,
                durability_interval_seconds=settings.recording.durability_interval_seconds,
                encrypted=settings.recording.audio_vault_encryption == "required",
            )
        except AudioVaultError as exc:
            with self._recording_lock:
                self._is_recording = False
            self._emit("transcription_error", {"message": str(exc)})
            return

        self._emit("recording_started", {"recording_id": session_id})

        t = threading.Thread(target=self._recording_loop, daemon=True, name="recording")
        self._recording_thread = t
        t.start()

    @handles(StopRecordingIntent)
    def handle_stop(self, intent: Any) -> None:
        if not self._is_recording:
            return
        self._recording_stop.set()

    @handles(CancelRecordingIntent)
    def handle_cancel(self, intent: Any) -> None:
        if not self._is_recording:
            return
        self._recording_stop.set()
        self._is_recording = False
        if self._spool is not None:
            self._spool.discard()
            self._spool = None
        self._emit("recording_stopped", {"cancelled": True})

    @handles(ToggleRecordingIntent)
    def handle_toggle(self, intent: Any) -> None:
        if self._is_recording:
            self.handle_stop(intent)
        else:
            self.handle_begin(intent)

    @handles(ImportAudioFileIntent)
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
                int16_audio = _decode_audio_file_to_int16(path)

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

    @handles(RetranscribeIntent)
    def handle_retranscribe(self, intent: Any) -> None:
        """Re-transcribe a transcript from its durable source audio."""
        transcript_id: int = intent.transcript_id
        if not transcript_id:
            self._emit("transcription_error", {"message": "No transcript ID provided"})
            return

        db = self._db_provider()
        if db is None:
            self._emit("transcription_error", {"message": "Database not available"})
            return

        assets = db.get_audio_assets_for_transcript(transcript_id)
        source_asset = next((asset for asset in assets if asset.role == "transcript_source"), None)
        wav_path = self._audio_cache.get_path(transcript_id) if self._audio_cache is not None else None
        if source_asset is None and wav_path is None:
            self._emit("transcription_error", {"message": "No cached audio for this transcript"})
            db.set_audio_cached(transcript_id, False)
            self._emit("transcript_updated", {"id": transcript_id})
            return

        def _retranscribe_worker() -> None:
            try:
                if source_asset is not None:
                    from src.services.audio_vault import AudioVaultManager

                    if source_asset.recording_id is None:
                        self._emit("transcription_error", {"message": "Cached audio is missing recording metadata"})
                        return
                    int16_audio = AudioVaultManager(db).load_audio(source_asset.recording_id)
                else:
                    int16_audio = _decode_audio_file_to_int16(wav_path)

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

                    self._audio_pipeline = AudioPipeline(sensitivity=settings.recording.vad_sensitivity)

                text, speech_duration_ms, _transcription_time_ms = transcribe(
                    int16_audio,
                    settings=settings,
                    local_model=self._asr_model,
                    audio_pipeline=self._audio_pipeline,
                )

                if not text.strip():
                    self._emit("transcription_error", {"message": "No speech detected in cached audio"})
                    return

                db.update_normalized_text(transcript_id, text)
                self._emit("transcript_updated", {"id": transcript_id})

                logger.info("Re-transcription complete for transcript %d: %d chars", transcript_id, len(text))

            except Exception as e:
                logger.exception("Re-transcription failed for transcript %d", transcript_id)
                self._emit("transcription_error", {"message": f"Re-transcription failed: {e}"})

        t = threading.Thread(target=_retranscribe_worker, daemon=True, name="retranscribe")
        t.start()

    @handles(TranscribeRecoveredRecordingIntent)
    def handle_transcribe_recovered(self, intent: Any) -> None:
        """Transcribe a recovered recording that survived a crash."""
        recording_id: str = intent.recording_id
        if not recording_id:
            self._emit("transcription_error", {"message": "No recording ID provided"})
            return

        db = self._db_provider()
        if db is None:
            self._emit("transcription_error", {"message": "Database not available"})
            return

        record = db.get_recording_session(recording_id)
        if record is None:
            self._emit("transcription_error", {"message": "Recovered recording not found"})
            return
        if record.status == "completed" and record.transcript_id is not None:
            self._emit("transcription_error", {"message": "Recording has already been transcribed"})
            return

        def _recovery_worker() -> None:
            try:
                from src.services.audio_vault import AudioVaultManager

                audio_data = AudioVaultManager(db).load_audio(recording_id)
                if len(audio_data) == 0:
                    db.mark_recording_status(recording_id, "failed", failure_reason="Recovered audio is empty")
                    self._emit("transcription_error", {"message": "Recovered audio is empty"})
                    return
                display_name = f"Recovered {record.started_at[:19]}" if record.started_at else "Recovered Recording"
                self._transcribe_and_store(
                    audio_data,
                    spool_path=Path(record.audio_path),
                    recording_id=recording_id,
                    display_name=display_name,
                )
                self._emit("audio_recovery_updated", {"recording_id": recording_id})
            except Exception as exc:
                logger.exception("Recovered recording transcription failed: %s", recording_id)
                db.mark_recording_status(recording_id, "failed", failure_reason=str(exc))
                self._emit("transcription_error", {"message": f"Recovered transcription failed: {exc}"})

        t = threading.Thread(target=_recovery_worker, daemon=True, name="transcribe-recovered")
        t.start()

    @handles(DeleteRecoveredRecordingIntent)
    def handle_delete_recovered(self, intent: Any) -> None:
        """Delete a recovered recording the user no longer wants."""
        recording_id: str = intent.recording_id
        db = self._db_provider()
        if db is None:
            return
        record = db.get_recording_session(recording_id)
        if record is None or record.status in {"active", "transcribing"}:
            return
        try:
            Path(record.audio_path).unlink(missing_ok=True)
            from src.core.secret_store import delete_audio_vault_key

            delete_audio_vault_key(recording_id)
        finally:
            db.mark_recording_status(recording_id, "deleted", finalized=True)
            self._emit("audio_recovery_updated", {"recording_id": recording_id})

    # --- Pipeline ---

    def _recording_loop(self) -> None:
        """Background thread: record audio → transcribe → store → emit."""
        spool = self._spool
        spool_path: Path | None = None
        recording_id = spool.session_id if spool is not None else None
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

            self._transcribe_and_store(audio_data, spool_path=spool_path, recording_id=recording_id)

        except Exception as e:
            logger.exception("Recording loop error")
            # Finalize spool on error so audio survives on disk
            if spool is not None and spool_path is None:
                try:
                    spool.finalize()
                except Exception:
                    pass
                self._spool = None
            if recording_id:
                db = self._db_provider()
                if db is not None:
                    db.mark_recording_status(recording_id, "failed", failure_reason=str(e), finalized=True)
            self._is_recording = False
            self._emit("recording_stopped", {"cancelled": False})
            self._emit("transcription_error", {"message": str(e)})

    def _transcribe_and_store(
        self,
        audio_data: Any,
        *,
        spool_path: Path | None = None,
        recording_id: str | None = None,
        source_tag: str | None = None,
        display_name: str | None = None,
    ) -> None:
        """Run transcription on audio data, store result, and emit events."""
        if self._shutdown_event.is_set():
            logger.debug("Transcription skipped — shutdown in progress")
            return

        from src.services.transcription_service import create_local_model, transcribe

        settings = self._settings_provider()
        db = self._db_provider()
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
                    if recording_id and db is not None:
                        db.mark_recording_status(recording_id, "failed", failure_reason="ASR model failed to load")
                    return

            if recording_id and db is not None:
                db.mark_recording_status(recording_id, "transcribing")

            # Lazy-create the AudioPipeline (holds cached Silero VAD session)
            if self._audio_pipeline is None:
                from src.services.audio_pipeline import AudioPipeline

                self._audio_pipeline = AudioPipeline(sensitivity=settings.recording.vad_sensitivity)

            text, speech_duration_ms, transcription_time_ms = transcribe(
                audio_data,
                settings=settings,
                local_model=self._asr_model,
                audio_pipeline=self._audio_pipeline,
            )

            if not text.strip():
                self._emit("transcription_error", {"message": "No speech detected"})
                if recording_id and db is not None:
                    db.mark_recording_status(recording_id, "failed", failure_reason="No speech detected")
                elif spool_path is not None:
                    self._cleanup_spool(spool_path)
                return

            # Store in database
            duration_ms = int(len(audio_data) / 16000 * 1000)
            transcript = None
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
                if recording_id and transcript and spool_path is not None:
                    size_bytes = spool_path.stat().st_size if spool_path.exists() else 0
                    record = db.get_recording_session(recording_id)
                    db.add_audio_asset(
                        recording_id=recording_id,
                        transcript_id=transcript.id,
                        role="transcript_source",
                        path=spool_path,
                        duration_ms=duration_ms,
                        size_bytes=size_bytes,
                        encrypted=bool(record.encrypted) if record is not None else False,
                        pinned=True,
                    )
                    db.set_audio_cached(transcript.id, True)
                    db.mark_recording_status(recording_id, "completed", transcript_id=transcript.id, finalized=True)

            self._emit(
                "transcription_complete",
                {
                    "text": text,
                    "id": transcript.id if transcript else None,
                    "duration_ms": duration_ms,
                    "speech_duration_ms": speech_duration_ms,
                },
            )

            # Schedule analytics insight generation if a threshold has been crossed.
            # Pass the new transcript's word count so InsightManager can apply
            # the explicit per-transcript minimum (ISS-119) instead of relying on
            # ambiguous aggregate-side effects.
            insight_manager = self._insight_manager_provider()
            if insight_manager is not None:
                new_words = len(text.split())
                insight_manager.maybe_schedule(new_transcript_words=new_words)

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

            # Legacy PCM spools can still be promoted to WAV. Vault recordings are already the source asset.
            if spool_path is not None and spool_path.suffix == ".pcm" and transcript is not None and self._audio_cache is not None:
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
                if recording_id is None:
                    self._cleanup_spool(spool_path)

            logger.info("Transcription complete: %d chars, %dms", len(text), duration_ms)

        except Exception as e:
            logger.exception("Transcription failed")
            if recording_id:
                db = self._db_provider()
                if db is not None:
                    db.mark_recording_status(recording_id, "failed", failure_reason=normalize_engine_error(e))
            else:
                self._cleanup_spool(spool_path)
            self.last_asr_error = normalize_engine_error(e)
            self._emit("transcription_error", {"message": self.last_asr_error})
        finally:
            self.is_transcribing = False

    @staticmethod
    def _cleanup_spool(spool_path: Path | None) -> None:
        """Delete a spool file if it exists (cache disabled or error path)."""
        if spool_path is not None:
            try:
                spool_path.unlink(missing_ok=True)
            except OSError:
                pass
