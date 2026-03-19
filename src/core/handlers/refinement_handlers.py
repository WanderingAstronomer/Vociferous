"""
RefinementHandlers — SLM-based transcript refinement intent.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Callable

from src.core.command_bus import handles
from src.core.intents.definitions import (
    BulkRefineTranscriptsIntent,
    CancelBulkRefinementIntent,
    CommitRefinementIntent,
    RefineTranscriptIntent,
)

if TYPE_CHECKING:
    from src.core.settings import VociferousSettings
    from src.database.db import TranscriptDB
    from src.services.slm_runtime import SLMRuntime

logger = logging.getLogger(__name__)


class RefinementHandlers:
    """Handles transcript refinement via the SLM runtime."""

    def __init__(
        self,
        *,
        db_provider: Callable[[], TranscriptDB | None],
        slm_runtime_provider: Callable[[], SLMRuntime | None],
        settings_provider: Callable[[], VociferousSettings],
        event_bus_emit: Callable,
        title_generator_provider: Callable[[], Any] = lambda: None,
    ) -> None:
        self._db_provider = db_provider
        self._slm_runtime_provider = slm_runtime_provider
        self._settings_provider = settings_provider
        self._emit = event_bus_emit
        self._title_generator_provider = title_generator_provider
        self._bulk_cancel = threading.Event()
        self._bulk_active = False

    def _fallback_raw_clipboard(self, transcript_id: int) -> None:
        """Copy raw transcript text to clipboard when refinement can't proceed.

        When auto-refine is on, the recording handler defers clipboard to us.
        If we can't refine, we MUST still copy the raw text — otherwise the
        user's text silently vanishes into the void.
        """
        settings = self._settings_provider()
        if not (settings.output.auto_refine and settings.output.auto_copy_to_clipboard):
            return
        db = self._db_provider()
        if not db:
            return
        transcript = db.get_transcript(transcript_id)
        if not transcript:
            return
        text = transcript.normalized_text or transcript.raw_text
        if text:
            from src.core.handlers.recording_handlers import _copy_to_system_clipboard

            _copy_to_system_clipboard(text)
            logger.info("Auto-copy fallback: copied raw text for transcript %d", transcript_id)

    def _resolve_instructions(self, provided: str, db: Any) -> str:
        instructions = provided or ""
        if not instructions.strip():
            settings = self._settings_provider()
            prompt_id = settings.refinement.default_prompt_transcript_id
            if prompt_id is not None:
                try:
                    prompt_t = db.get_transcript(prompt_id)
                    if prompt_t:
                        instructions = prompt_t.normalized_text or prompt_t.raw_text or ""
                except Exception as e:
                    logger.warning("Failed to resolve default prompt (ID %d): %s", prompt_id, e)
        return instructions

    @handles(RefineTranscriptIntent)
    def handle_refine(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            self._emit("refinement_error", {"message": "Database not available"})
            return

        slm_runtime = self._slm_runtime_provider()
        if not slm_runtime:
            self._emit("refinement_error", {"message": "Refinement is not configured. Enable it in Settings."})
            self._fallback_raw_clipboard(intent.transcript_id)
            return

        from src.services.slm_types import SLMState

        state = slm_runtime.state
        if state == SLMState.DISABLED:
            self._emit(
                "refinement_error",
                {"message": "Refinement is disabled. Enable it in Settings and ensure a model is downloaded."},
            )
            self._fallback_raw_clipboard(intent.transcript_id)
            return
        if state == SLMState.LOADING:
            self._emit(
                "refinement_error",
                {"message": "The refinement model is still loading. Please wait a moment and try again."},
            )
            self._fallback_raw_clipboard(intent.transcript_id)
            return
        if state == SLMState.ERROR:
            self._emit(
                "refinement_error",
                {
                    "message": "The refinement model failed to load. Try restarting the engine in Settings → Maintenance."
                },
            )
            self._fallback_raw_clipboard(intent.transcript_id)
            return
        if state == SLMState.INFERRING:
            self._emit(
                "refinement_error",
                {"message": "A refinement is already in progress. Please wait for it to finish."},
            )
            self._fallback_raw_clipboard(intent.transcript_id)
            return
        if self._bulk_active:
            self._emit(
                "refinement_error",
                {"message": "A bulk refinement is in progress. Please wait for it to finish."},
            )
            self._fallback_raw_clipboard(intent.transcript_id)
            return
        if state != SLMState.READY:
            self._emit("refinement_error", {"message": f"Refinement model not ready (state: {state.value})"})
            self._fallback_raw_clipboard(intent.transcript_id)
            return

        transcript = db.get_transcript(intent.transcript_id)
        if not transcript:
            self._emit("refinement_error", {"message": "Transcript not found"})
            return

        resolved_instructions = self._resolve_instructions(intent.instructions, db)

        self._emit(
            "refinement_started",
            {
                "transcript_id": intent.transcript_id,
                "level": intent.level,
            },
        )

        def do_refine() -> None:
            start_time = time.monotonic()
            _slm = self._slm_runtime_provider()
            try:
                # Refine from the immutable original, never a previous variant.
                text = transcript.normalized_text or transcript.raw_text

                self._emit(
                    "refinement_progress",
                    {
                        "transcript_id": intent.transcript_id,
                        "status": "inferring",
                        "message": "Running inference…",
                    },
                )

                refined = _slm.refine_text_sync(
                    text,
                    level=intent.level,
                    instructions=resolved_instructions,
                )

                elapsed = round(time.monotonic() - start_time, 1)

                # Persist refinement processing time for analytics
                _db = self._db_provider()
                if _db:
                    _db.update_refinement_time(intent.transcript_id, int(elapsed * 1000))

                self._emit(
                    "refinement_complete",
                    {
                        "transcript_id": intent.transcript_id,
                        "text": refined,
                        "level": intent.level,
                        "elapsed_seconds": elapsed,
                    },
                )

                # If auto-refine + auto-copy, the recording handler deferred
                # the clipboard write — do it now with the refined text.
                settings = self._settings_provider()
                if settings.output.auto_refine and settings.output.auto_copy_to_clipboard:
                    from src.core.handlers.recording_handlers import _copy_to_system_clipboard

                    _copy_to_system_clipboard(refined)
            except Exception as e:
                logger.exception("Refinement failed for transcript %d", intent.transcript_id)
                self._emit(
                    "refinement_error",
                    {
                        "transcript_id": intent.transcript_id,
                        "message": str(e),
                    },
                )
                self._fallback_raw_clipboard(intent.transcript_id)

        t = threading.Thread(target=do_refine, daemon=True, name="refine")
        t.start()

    @handles(CommitRefinementIntent)
    def handle_commit_refinement(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            self._emit("refinement_error", {"message": "Database not available"})
            return

        transcript = db.get_transcript(intent.transcript_id)
        if not transcript:
            self._emit("refinement_error", {"message": "Transcript not found"})
            return

        db.update_normalized_text(intent.transcript_id, intent.text)
        db.add_system_tag_to_transcript(intent.transcript_id, "Refined")

        updated = db.get_transcript(intent.transcript_id)
        if updated:
            self._emit(
                "transcript_updated",
                {
                    "id": intent.transcript_id,
                    "tags": [
                        {"id": t.id, "name": t.name, "color": t.color, "is_system": t.is_system} for t in updated.tags
                    ],
                },
            )

        settings = self._settings_provider()
        if settings.output.auto_retitle_on_refine:
            title_gen = self._title_generator_provider()
            if title_gen is not None:
                title_gen.schedule(intent.transcript_id, intent.text)

    # --- Bulk refinement ---

    def _validate_slm_ready(self) -> tuple[Any, str | None]:
        """Check SLM is ready; return (runtime, error_message_or_None)."""
        slm_runtime = self._slm_runtime_provider()
        if not slm_runtime:
            return None, "Refinement is not configured. Enable it in Settings."
        from src.services.slm_types import SLMState

        state = slm_runtime.state
        if state == SLMState.DISABLED:
            return None, "Refinement is disabled. Enable it in Settings and ensure a model is downloaded."
        if state == SLMState.LOADING:
            return None, "The refinement model is still loading. Please wait a moment and try again."
        if state == SLMState.ERROR:
            return None, "The refinement model failed to load. Check Settings to verify a model is downloaded."
        if state == SLMState.INFERRING:
            return None, "A refinement is already in progress. Please wait for it to finish."
        if state != SLMState.READY:
            return None, f"Refinement model not ready (state: {state.value})"
        return slm_runtime, None

    @handles(BulkRefineTranscriptsIntent)
    def handle_bulk_refine(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            self._emit("bulk_refinement_error", {"message": "Database not available"})
            return

        transcript_ids: tuple[int, ...] = intent.transcript_ids
        if not transcript_ids:
            self._emit("bulk_refinement_error", {"message": "No transcripts provided"})
            return

        slm_runtime, err = self._validate_slm_ready()
        if err:
            self._emit("bulk_refinement_error", {"message": err})
            return

        if self._bulk_active:
            self._emit(
                "bulk_refinement_error",
                {"message": "A bulk refinement is already in progress."},
            )
            return

        # Filter out already-refined transcripts when requested
        if intent.skip_refined:
            already_refined = db.get_ids_with_system_tag("Refined", transcript_ids)
            if already_refined:
                transcript_ids = tuple(tid for tid in transcript_ids if tid not in already_refined)
                if not transcript_ids:
                    self._emit(
                        "bulk_refinement_complete",
                        {"completed": 0, "total": 0, "failed": 0, "cancelled": False},
                    )
                    return

        total = len(transcript_ids)
        self._bulk_active = True
        self._bulk_cancel.clear()

        self._emit(
            "bulk_refinement_started",
            {"transcript_ids": list(transcript_ids), "total": total, "level": intent.level},
        )

        resolved_instructions = self._resolve_instructions(intent.instructions, db)

        def do_bulk() -> None:
            completed = 0
            failed = 0
            try:
                for tid in transcript_ids:
                    if self._bulk_cancel.is_set():
                        logger.info("Bulk refinement cancelled after %d/%d", completed, total)
                        break

                    _db = self._db_provider()
                    if not _db:
                        failed += 1
                        continue

                    transcript = _db.get_transcript(tid)
                    if not transcript:
                        logger.warning("Bulk refine: transcript %d not found, skipping", tid)
                        failed += 1
                        self._emit(
                            "bulk_refinement_progress",
                            {
                                "completed": completed,
                                "failed": failed,
                                "total": total,
                                "current_transcript_id": tid,
                                "skipped": True,
                            },
                        )
                        continue

                    text = transcript.normalized_text or transcript.raw_text
                    try:
                        _slm = self._slm_runtime_provider()
                        refine_start = time.monotonic()
                        refined = _slm.refine_text_sync(
                            text,
                            level=intent.level,
                            instructions=resolved_instructions,
                        )
                        refine_elapsed_ms = int((time.monotonic() - refine_start) * 1000)
                    except Exception as e:
                        logger.exception("Bulk refine: inference failed for transcript %d", tid)
                        failed += 1
                        self._emit(
                            "bulk_refinement_progress",
                            {
                                "completed": completed,
                                "failed": failed,
                                "total": total,
                                "current_transcript_id": tid,
                                "error": str(e),
                            },
                        )
                        continue

                    # Auto-commit: persist + tag + timing
                    _db.update_normalized_text(tid, refined)
                    _db.add_system_tag_to_transcript(tid, "Refined")
                    _db.update_refinement_time(tid, refine_elapsed_ms)
                    completed += 1

                    updated = _db.get_transcript(tid)
                    if updated:
                        self._emit(
                            "transcript_updated",
                            {
                                "id": tid,
                                "tags": [
                                    {"id": t.id, "name": t.name, "color": t.color, "is_system": t.is_system}
                                    for t in updated.tags
                                ],
                            },
                        )

                    # Auto-retitle if enabled
                    settings = self._settings_provider()
                    if settings.output.auto_retitle_on_refine:
                        title_gen = self._title_generator_provider()
                        if title_gen is not None:
                            title_gen.schedule(tid, refined)

                    self._emit(
                        "bulk_refinement_progress",
                        {"completed": completed, "failed": failed, "total": total, "current_transcript_id": tid},
                    )

                self._emit(
                    "bulk_refinement_complete",
                    {
                        "completed": completed,
                        "total": total,
                        "failed": failed,
                        "cancelled": self._bulk_cancel.is_set(),
                    },
                )
            except Exception as e:
                logger.exception("Bulk refinement loop crashed")
                self._emit(
                    "bulk_refinement_error",
                    {"message": str(e), "completed": completed, "total": total},
                )
            finally:
                self._bulk_active = False

        t = threading.Thread(target=do_bulk, daemon=True, name="bulk-refine")
        t.start()

    @handles(CancelBulkRefinementIntent)
    def handle_cancel_bulk_refine(self, intent: Any) -> None:
        if not self._bulk_active:
            return
        self._bulk_cancel.set()
        logger.info("Bulk refinement cancel requested")
