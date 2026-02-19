"""
RefinementHandlers — SLM-based transcript refinement intent.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Callable

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

    def handle_refine(self, intent: Any) -> None:
        db = self._db_provider()
        if not db:
            self._emit("refinement_error", {"message": "Database not available"})
            return

        slm_runtime = self._slm_runtime_provider()
        if not slm_runtime:
            self._emit("refinement_error", {"message": "Refinement is not configured. Enable it in Settings."})
            return

        from src.services.slm_types import SLMState

        state = slm_runtime.state
        if state == SLMState.DISABLED:
            self._emit(
                "refinement_error",
                {"message": "Refinement is disabled. Enable it in Settings and ensure a model is downloaded."},
            )
            return
        if state == SLMState.LOADING:
            self._emit(
                "refinement_error",
                {"message": "The refinement model is still loading. Please wait a moment and try again."},
            )
            return
        if state == SLMState.ERROR:
            self._emit(
                "refinement_error",
                {"message": "The refinement model failed to load. Check Settings to verify a model is downloaded."},
            )
            return
        if state == SLMState.INFERRING:
            self._emit(
                "refinement_error",
                {"message": "A refinement is already in progress. Please wait for it to finish."},
            )
            return
        if state != SLMState.READY:
            self._emit("refinement_error", {"message": f"Refinement model not ready (state: {state.value})"})
            return

        transcript = db.get_transcript(intent.transcript_id)
        if not transcript:
            self._emit("refinement_error", {"message": "Transcript not found"})
            return

        self._emit(
            "refinement_started",
            {
                "transcript_id": intent.transcript_id,
                "level": intent.level,
            },
        )

        def do_refine() -> None:
            start_time = time.monotonic()
            _db = self._db_provider()
            _slm = self._slm_runtime_provider()
            settings = self._settings_provider()
            try:
                # ALWAYS refine from the immutable original, never a previous variant.
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
                    instructions=intent.instructions,
                )

                elapsed = round(time.monotonic() - start_time, 1)

                variant = _db.add_variant(
                    intent.transcript_id,
                    f"refinement_L{intent.level}",
                    refined,
                    model_id=settings.refinement.model_id,
                    set_current=True,
                )

                # Prune old refinement variants: keep only the 3 most recent.
                _db.prune_refinement_variants(intent.transcript_id, keep=3)

                self._emit(
                    "refinement_complete",
                    {
                        "transcript_id": intent.transcript_id,
                        "variant_id": variant.id,
                        "text": refined,
                        "level": intent.level,
                        "elapsed_seconds": elapsed,
                    },
                )

                # Re-title after refinement if the setting is enabled
                if settings.output.auto_retitle_on_refine:
                    title_gen = self._title_generator_provider()
                    if title_gen is not None:
                        title_gen.schedule(intent.transcript_id, refined)
            except Exception as e:
                logger.exception("Refinement failed for transcript %d", intent.transcript_id)
                self._emit(
                    "refinement_error",
                    {
                        "transcript_id": intent.transcript_id,
                        "message": str(e),
                    },
                )

        t = threading.Thread(target=do_refine, daemon=True, name="refine")
        t.start()
