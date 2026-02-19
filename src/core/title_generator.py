"""
Title Generator — Background SLM-based auto-titling for transcripts.

Follows the InsightManager pattern: fire-and-forget background thread,
no blocking, emits 'transcript_updated' when the title is ready.

Trigger: called after each transcription_complete in the recording pipeline.
Guard rails:
    - Only fires if SLM is READY (not INFERRING, not DISABLED).
    - Only fires if text length is within bounds (100–30,000 chars).
    - One generation at a time per transcript (simple set-based dedup).
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Callable

from src.core.constants import TitleGeneration

if TYPE_CHECKING:
    from src.database.db import TranscriptDB
    from src.services.slm_runtime import SLMRuntime

logger = logging.getLogger(__name__)

_TITLE_SYSTEM_PROMPT = """\
You generate short, descriptive titles for speech-to-text transcriptions.

Rules:
- Output ONLY the title. No quotes, no prefix, no explanation.
- 3 to 8 words maximum.
- Capture the main topic or intent of the text.
- Use title case.
- Never begin with "Transcript" or "Recording".
- If the text covers multiple topics, pick the dominant one.
- Be specific, not generic. "Budget Review for Q3" is good. "Meeting Notes" is bad."""


class TitleGenerator:
    """
    Generates short SLM-based titles for transcripts in a background thread.

    Usage:
        generator.schedule(transcript_id, text)

    After generation completes, the display_name is written to the DB and
    a 'transcript_updated' event is emitted for the frontend to pick up.
    """

    def __init__(
        self,
        *,
        slm_runtime_provider: Callable[[], "SLMRuntime | None"],
        db_provider: Callable[[], "TranscriptDB | None"],
        event_emitter: Callable[[str, dict], None],
    ) -> None:
        self._slm_provider = slm_runtime_provider
        self._db_provider = db_provider
        self._emit = event_emitter

        self._lock = threading.Lock()
        self._pending: set[int] = set()  # transcript IDs currently being titled

    def schedule(self, transcript_id: int, text: str) -> None:
        """
        Schedule title generation for a transcript if conditions are met.

        Conditions:
        1. Text length is within bounds.
        2. SLM runtime is loaded and READY.
        3. No title generation is already in flight for this transcript.
        """
        text_len = len(text)
        if text_len < TitleGeneration.MIN_TEXT_CHARS:
            logger.debug(
                "Title gen: text too short (%d chars < %d min), skipping transcript %d",
                text_len, TitleGeneration.MIN_TEXT_CHARS, transcript_id,
            )
            return

        with self._lock:
            if transcript_id in self._pending:
                logger.debug("Title gen: already in flight for transcript %d", transcript_id)
                return

            slm = self._slm_provider()
            if slm is None:
                logger.debug("Title gen: SLM unavailable, skipping transcript %d", transcript_id)
                return

            from src.services.slm_types import SLMState

            if slm.state != SLMState.READY:
                logger.debug("Title gen: SLM not ready (%s), skipping transcript %d", slm.state, transcript_id)
                return

            self._pending.add(transcript_id)

        logger.info("Title gen: scheduling for transcript %d (%d chars)", transcript_id, text_len)
        t = threading.Thread(
            target=self._generate_task,
            args=(transcript_id, text),
            daemon=True,
            name=f"title-gen-{transcript_id}",
        )
        t.start()

    def batch_retitle(self) -> None:
        """
        Batch-retitle all untitled transcripts. Runs on a background thread.
        Emits batch_retitle_progress events so the frontend can track progress.
        Skips transcripts that are too short or too long per TitleGeneration constants.
        """
        db = self._db_provider()
        if db is None:
            self._emit("batch_retitle_progress", {"status": "error", "message": "Database not available"})
            return

        slm = self._slm_provider()
        if slm is None:
            self._emit("batch_retitle_progress", {"status": "error", "message": "SLM runtime not available"})
            return

        from src.services.slm_types import SLMState

        if slm.state != SLMState.READY:
            self._emit("batch_retitle_progress", {
                "status": "error",
                "message": f"SLM not ready (state: {slm.state.value}). Enable refinement and ensure a model is downloaded.",
            })
            return

        untitled = db.get_untitled_transcripts()
        total = len(untitled)
        if total == 0:
            self._emit("batch_retitle_progress", {"status": "complete", "processed": 0, "skipped": 0, "total": 0})
            return

        t = threading.Thread(
            target=self._batch_retitle_task,
            args=(untitled,),
            daemon=True,
            name="batch-retitle",
        )
        t.start()

    def _batch_retitle_task(self, transcripts: list) -> None:
        """Background thread: iterate untitled transcripts, generate titles sequentially."""
        total = len(transcripts)
        processed = 0
        skipped = 0

        self._emit("batch_retitle_progress", {
            "status": "started",
            "total": total,
            "processed": 0,
            "skipped": 0,
        })

        for i, transcript in enumerate(transcripts):
            text = transcript.normalized_text or transcript.raw_text or ""
            text_len = len(text)

            # Skip logic: too short or too long
            if text_len < TitleGeneration.MIN_TEXT_CHARS or text_len > TitleGeneration.MAX_TEXT_CHARS:
                skipped += 1
                logger.debug(
                    "Batch retitle: skipping transcript %d (%d chars — out of bounds)",
                    transcript.id, text_len,
                )
                self._emit("batch_retitle_progress", {
                    "status": "progress",
                    "total": total,
                    "processed": processed,
                    "skipped": skipped,
                    "current": i + 1,
                })
                continue

            try:
                slm = self._slm_provider()
                if slm is None:
                    logger.warning("Batch retitle: SLM disappeared at transcript %d", transcript.id)
                    break

                from src.services.slm_types import SLMState

                if slm.state != SLMState.READY:
                    logger.warning("Batch retitle: SLM no longer ready at transcript %d", transcript.id)
                    # Wait a moment and retry once — SLM might be between calls
                    import time
                    time.sleep(2)
                    if slm.state != SLMState.READY:
                        logger.warning("Batch retitle: SLM still not ready, aborting batch")
                        break

                input_text = text[:TitleGeneration.MAX_TEXT_CHARS]
                title = slm.generate_custom_sync(
                    system_prompt=_TITLE_SYSTEM_PROMPT,
                    user_prompt=input_text,
                    max_tokens=TitleGeneration.MAX_TITLE_TOKENS,
                    temperature=TitleGeneration.TEMPERATURE,
                )

                if not title or not title.strip():
                    skipped += 1
                    logger.warning("Batch retitle: empty title for transcript %d", transcript.id)
                else:
                    title = title.strip().strip('"').strip("'").strip()
                    if "\n" in title:
                        title = title.split("\n")[0].strip()

                    db = self._db_provider()
                    if db is not None:
                        db.update_display_name(transcript.id, title)
                        self._emit("transcript_updated", {"id": transcript.id})
                        processed += 1
                        logger.info("Batch retitle: transcript %d → '%s'", transcript.id, title)

            except Exception:
                logger.exception("Batch retitle: failed for transcript %d", transcript.id)
                skipped += 1

            self._emit("batch_retitle_progress", {
                "status": "progress",
                "total": total,
                "processed": processed,
                "skipped": skipped,
                "current": i + 1,
            })

        self._emit("batch_retitle_progress", {
            "status": "complete",
            "total": total,
            "processed": processed,
            "skipped": skipped,
        })
        logger.info("Batch retitle complete: %d processed, %d skipped out of %d total", processed, skipped, total)

    def _generate_task(self, transcript_id: int, text: str) -> None:
        """Background thread: generate title via SLM, write to DB, emit event."""
        try:
            slm = self._slm_provider()
            if slm is None:
                logger.warning("Title gen: SLM disappeared before generation for transcript %d", transcript_id)
                return

            from src.services.slm_types import SLMState

            if slm.state != SLMState.READY:
                logger.warning("Title gen: SLM no longer ready (%s) for transcript %d", slm.state, transcript_id)
                return

            # Truncate input to the max bound — don't feed a whole novel
            input_text = text[:TitleGeneration.MAX_TEXT_CHARS]

            logger.info("Title gen: running SLM inference for transcript %d...", transcript_id)
            title = slm.generate_custom_sync(
                system_prompt=_TITLE_SYSTEM_PROMPT,
                user_prompt=input_text,
                max_tokens=TitleGeneration.MAX_TITLE_TOKENS,
                temperature=TitleGeneration.TEMPERATURE,
            )

            if not title or not title.strip():
                logger.warning("Title gen: SLM returned empty title for transcript %d", transcript_id)
                return

            # Clean up: strip quotes the model might wrap around the title
            title = title.strip().strip('"').strip("'").strip()

            # Sanity: if the model hallucinated a paragraph, take just the first line
            if "\n" in title:
                title = title.split("\n")[0].strip()

            # Write to DB
            db = self._db_provider()
            if db is None:
                logger.warning("Title gen: DB unavailable, cannot save title for transcript %d", transcript_id)
                return

            db.update_display_name(transcript_id, title)

            # Notify frontend
            self._emit("transcript_updated", {"id": transcript_id})
            logger.info("Title gen: transcript %d titled '%s'", transcript_id, title)

        except Exception:
            logger.exception("Title gen: failed for transcript %d", transcript_id)
        finally:
            with self._lock:
                self._pending.discard(transcript_id)
