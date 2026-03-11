# Vociferous Changelog

## v5.11.0 — TranscriptsView Contextual Export

**Date:** 2026-03-11
**Status:** Feature
**Issue:** ISS-093

### Added
- **Export button in TranscriptsView action bar** — Select one or more transcripts, click Export, pick a format from the popover (Markdown, JSON, CSV, Plain Text), and save via native file dialog. Export respects current sort order. Single-transcript exports use the transcript title as filename.
- **Shared export utilities** (`frontend/src/lib/exportUtils.ts`) — Extracted export formatting from MaintenanceCard into a properly typed shared module. Markdown formatter upgraded with display_name titles, human-readable durations, and formatted timestamps.

### Changed
- **MaintenanceCard refactored** — Now imports from shared `exportUtils.ts` instead of owning ~91 lines of inline formatting. "Export All" in Maintenance continues to work unchanged as the bulk fallback.

### Technical Notes
- No new backend endpoint or intent needed — export uses the existing `POST /api/export` (native save dialog) and formats data entirely frontend-side from already-loaded transcript objects.
- Format picker is a position-anchored popover following the same pattern as the tag assignment popover.
- Escape key and click-outside dismiss the export popover.

---

## v5.10.8 — UserView Overhaul, Analytics Audit, SettingsView Polish, Clipboard Fix

**Date:** 2026-03-11
**Status:** Feature / Bugfix / Polish
**Issues:** ISS-085, ISS-088, ISS-089, ISS-090, ISS-091, ISS-092

### Changed
- **UserView restructured into Dashboard + Deep Dive tabs** (ISS-092) — Killed the radar chart and distribution bell curves. Dashboard shows two summary cards ("Your Voice" + "Refinement Impact") with streaks, top filler word, and WPM. Deep Dive has four honest sections: Productivity, Speech Quality (filler bar chart), Readability (before/after FK delta), and Trends (speed + session length line charts). Every metric either works or is gone.
- **Usage stats overhaul** (ISS-085) — WPM now uses VAD-based `speech_duration_ms` as denominator. Silence ratio only computed on transcripts with VAD data, with "based on X of Y" caveat. Dead metrics killed (`avg_word_length`, `long_word_ratio`). Added: `total_speech_seconds`, `avg_wpm`, per-word filler breakdown (`filler_counts`), current/longest streak computation, trend time-series data.
- **Activity heatmap moved above tabs** (ISS-089) — Renders once between the AI insight paragraph and the tab bar instead of being duplicated inside each tab.
- **About card rewritten** (ISS-090) — Body text now reflects the full dictation-to-document pipeline, not just "speech to text".
- **TranscriptsView rendering switched to `style:display`** (ISS-088) — No longer destroyed on navigation. Default page size changed to 25, options to 10/25/50.

### Added
- **`countFillersByWord()`** in `textAnalysis.ts` — Frontend filler breakdown for the Deep Dive horizontal bar chart.
- **Calculation detail labels** — Caveat annotations on silence ratio, filler density, and WPM explaining data coverage and approximation boundaries.
- **SettingsView polish batch** (ISS-091) — "Hover for info" hint above tabs, tooltip audit across all 5 tabs, custom +/- stepper buttons on audio cache input (hides native spinners), maintenance button layout repositioned (Clear All left, Export right with primary variant).

### Fixed
- **Clipboard copies raw text when auto-refine is enabled** — `recording_handlers.py` was unconditionally copying to clipboard on transcription complete, before refinement had a chance to run. Now skips clipboard when `auto_refine` is on. `refinement_handlers.py` copies the refined text to clipboard after refinement completes (when both `auto_refine` and `auto_copy_to_clipboard` are enabled).

### Removed
- **RadarChart.svelte** — Dead. Mixed-unit normalized axes were dishonest.
- **DistributionChart.svelte** — Dead. Bell curves looked impressive but told users nothing actionable.
- **Polysyllabic word ratio, lexical complexity, average word length, long word ratio** — Removed from display and/or computation. Nobody cares.

### Technical Notes
- `usage_stats.py`: `compute_usage_stats()` signature unchanged but return dict gains `total_speech_seconds`, `avg_wpm`, `filler_counts`, `current_streak`, `longest_streak`, trend arrays. Dead keys removed.
- `UserView.svelte`: ~475 lines changed. Complete tab restructure. New chart components inline (filler bar chart, trend line charts via canvas).
- `test_usage_stats.py`: Test shapes updated for new return keys. Added coverage for VAD silence filtering, WPM computation, filler breakdown, streak calculation.

---

## v5.10.7 — Architecture Audit Cleanup

**Date:** 2026-03-11
**Status:** Hotfix / Cleanup

### Removed
- **Dead event bridge entry** — `batch_retitle_progress` was registered in the
  WebSocket event bridge but was never emitted by any Python code and never
  subscribed to on the frontend. Removed.

### Fixed
- **Unused variable** — `info` return value from `faster-whisper`'s `transcribe()`
  replaced with `_` in `transcription_service.py`.

---

**Vociferous** is a cross-platform speech-to-text application with offline transcription powered by CTranslate2 (via faster-whisper) and text refinement via a local Small Language Model.

## v5.10.6 — RefineView & TranscriptionsView Polish, Recording Rail Indicator

**Date:** 2026-03-11
**Status:** Feature / Bugfix

### Fixed
- **RefineView transcript switch guard** — Clicking "Refine" on a transcript in TranscriptionsView while a refinement was already in progress would silently overwrite the active transcript, making the Accept/Copy buttons unreachable forever. Navigation requests are now blocked (with a toast) when `isRefining` is true or when an unaccepted refinement result is pending.

### Added
- **Bulk refinement progress bar in RefineView** — While a bulk refinement is running, a slim progress card (spinner + "Bulk refine: X of Y" + progress bar + cancel button) appears above the Instructions panel in RefineView. RefineView stays mounted across navigation so this bar persists regardless of which view you're on. Navigating away from TranscriptionsView naturally hides its own progress bar (it unmounts), while RefineView remains the live status surface.
- **IconRail recording indicator** — The Transcribe rail button pulses red with a 2s breathing animation when a recording is active and you're on any other view. The left accent bar also turns red. Tooltip changes to "Recording in progress". Uses the existing `recordingActive` state from App.svelte.
- **Analytics delta label improvements** — "Avg Sentence" → "Avg Sentence Length", "Grade" → "FK Score", "Fillers" → "Filler Words". All five metric labels now have styled hover tooltips explaining what each metric measures.
- **Markdown toggle in RefineView action bar** — Added a "Markdown" toggle (next to the existing "Diff" toggle) to render both text panels as formatted markdown. Uses the same `display.render_markdown_in_editor` config setting initialized on mount.
- **New `Tooltip` component** (`frontend/src/lib/components/Tooltip.svelte`) — Reusable cursor-following tooltip rendered via a fixed-position overlay. Dark-themed, max-width 280px, uses Svelte 5 snippet slot.

### Changed
- **TranscriptionsView controls layout reorganized** — Sort buttons moved to the left, page navigation (Prev / X of Y / Next) moved to the center of the controls row (visible without scrolling regardless of page size), per-page selector stays on the right. Total transcript count moved from the top-left to a blue accent footer at the bottom center of the card list.

### Technical Notes
- `IconRail.svelte`: Added `isRecording?: boolean` prop. New `.recording` CSS class + `recording-pulse` keyframe animation.
- `App.svelte`: Passes `isRecording={recordingActive}` to `<IconRail>`.
- `RefineView.svelte`: Added `bulkRefineActive/Completed/Failed/Total` state, four new WebSocket subscriptions (`bulk_refinement_started/progress/complete/error`), cancel button calling `cancelBulkRefinement()`, and the `$effect` guard.
- `TranscriptsView.svelte`: Controls row fully restructured. Bottom-of-list total count replaces the old per-page-scroll pagination.

---

## v5.10.5 — RefineView Overhaul: Diff Highlighting, Analytics Delta, Prompt UX

**Date:** 2026-03-11
**Status:** Feature / Polish

### Changed
- **Removed transcript selector dropdown** — RefineView no longer loads all transcripts into a picker dropdown. Users navigate to refine from TranscribeView or TranscriptionsView, which is the natural flow. When no transcript is pending, an EmptyState guides the user. Eliminated ~80 lines of picker UI and the `loadTranscripts()` call.
- **Centered card titles** — "Original Transcript" and "Refined / AI Suggestion" headings are now horizontally centered with action icons balanced on each side.
- **Markdown rendering respects setting** — Both text panels now conditionally render MarkdownBody or raw pre-wrapped text based on the `display.render_markdown_in_editor` config setting (introduced in v5.10.4). Raw text is the default.
- **Replaced native `<select>` with `CustomSelect`** for saved prompts — fixes the white-on-dark theme rendering issue caused by GTK+WebKit ignoring CSS on native `<option>` elements.
- **Saved prompt selection is tracked** — The dropdown now shows which prompt is currently loaded instead of always resetting to "Load a saved prompt…".
- **Discard button is always red** — Changed from `danger-reveal` (only red on hover) to `destructive` variant (always visible as destructive action).

### Added
- **Diff highlighting toggle** — After refinement, a "Diff" toggle in the action bar (and a diff icon in the refined panel header) toggles a word-level diff view showing exactly what changed. Uses the `diff` npm package for word-level comparison. Added text is highlighted in accent blue, removed text in red with strikethrough.
- **Analytics delta card** — After refinement, a horizontal metrics strip appears between the comparison panels and the instructions card. Shows before→after deltas for: word count, sentence count, average sentence length, Flesch-Kincaid grade, and filler count.
- **Edit prompt button** — When a saved prompt is selected, an edit icon appears next to the dropdown that navigates to EditView for that prompt.
- **New `DiffView` component** (`frontend/src/lib/components/DiffView.svelte`) — Reusable word-level diff renderer using the `diff` library.

### Technical Notes
- `RefineView.svelte`: Complete rewrite of template and significant script refactoring. Removed `transcripts`, `showPicker`, `loadingTranscripts`, `loadTranscripts()`, `truncateText()`. Added `showDiff`, `renderMarkdown`, `transcriptName`, `selectedPromptId`, `origMetrics`/`refMetrics` derived analytics, `delta()`/`deltaF()` helpers, `editSelectedPrompt()`.
- Installed `diff` and `@types/diff` npm packages.
- `computeTextMetrics()` from `textAnalysis.ts` drives the analytics delta card.

---

## v5.10.4 — Markdown Preview in Editor & Compound Continue Fix

**Date:** 2026-03-11
**Status:** Feature / Bugfix

### Fixed
- **Continue button missing on compound transcripts** — After appending to an existing transcript (via "Continue" flow), the `viewState` transitions to `"viewing"` rather than `"ready"`. The Continue button was only rendered for `viewState === "ready"`, so it disappeared on compound transcripts. Now shows for both `"ready"` and `"viewing"` states.

### Added
- **Markdown preview toggle in EditView** — New "Markdown" toggle in the EditView header (next to analytics toggle) renders the transcript text as formatted markdown instead of raw text in the textarea. Useful for reviewing refined transcripts that contain headings, lists, and formatting.
- **"Markdown in Editor" setting in Settings > Appearance** — New persistent setting (`display.render_markdown_in_editor`, default: off) controls the default state of the markdown preview toggle when opening EditView. Per-session toggling still works independently.

### Technical Notes
- `TranscribeView.svelte`: Changed Continue button condition from `viewState === "ready"` to `viewState === "ready" || viewState === "viewing"`.
- `EditView.svelte`: Added `MarkdownBody` import, `showMarkdownPreview` state (initialized from config on mount), toggle UI, and conditional textarea/MarkdownBody rendering.
- `SettingsView.svelte`: Added `ToggleSwitch` import and "Markdown in Editor" toggle row in the Appearance tab.
- `src/core/settings.py`: Added `render_markdown_in_editor: bool = False` to `DisplaySettings` model.

---

## v5.10.3 — Recording UX & Append Auto-Refine Fixes

**Date:** 2026-03-11
**Status:** Hotfix / Polish

### Fixed
- **Navigation lock during recording removed** — `App.svelte` was locking all view navigation when a recording started, preventing the user from viewing other views (transcripts, settings, dashboard) while recording was in progress. This was intended as a safeguard but unnecessary: TranscribeView stays mounted via `display: none/block`, so recording state is preserved regardless of which view is visible. Recording can safely proceed in the background. Removed the `isNavigationLocked` assignment from the `recording_started` event handler.
- **Missing "Continue" button in TranscribeView** — After a transcription completes and is displayed in TranscribeView ready state, the action bar showed "Append to Previous" but no "Continue" button to queue up append mode for the *next* recording targeting the current transcript. Added `queueContinueMode()` function and a new "Continue" button that calls `nav.navigateToAppendMode(transcriptId)`, queuing the next recording to append to the current one.
- **Auto-refine not firing during append** — When appending a new recording to an existing transcript (via "Continue" or from TranscriptsView "Continue Recording"), the transcript was appended but auto-refine was never triggered (the code path returned early). Now auto-refine is dispatched on the target transcript if enabled, refining the combined text after append succeeds.

### Technical Notes
- `App.svelte`: Removed `nav.isNavigationLocked = true/false` from `recording_started` and `recording_stopped` event handlers.
- `TranscribeView.svelte`: Added `queueContinueMode()` and "Continue" button in the action bar (visible in `ready` state). Updated both append code paths (`appendToPrevious` and the `append_to_transcript` handler in `transcription_complete` event) to fire auto-refine if enabled.

---

## v5.10.2 — Architecture Audit: Dependency Inversion & Async Compliance

**Date:** 2026-03-11
**Status:** Hotfix / Architecture

### Fixed
- **Dependency inversion in `APP_VERSION`** — `_resolve_app_version()` and `APP_VERSION` were defined in `src/api/system.py` but imported by `src/core/application_coordinator.py`. That's a layer violation: core should never import from api. Moved both to `src/core/constants.py`. `system.py` now imports from the correct layer.
- **Blocking DB calls in async tag routes** — `PUT /api/tags/{id}` and `DELETE /api/tags/{id}` were `async def` but called `coordinator.db.get_tag()` (synchronous SQLite) plus dispatched to CommandBus handlers (also synchronous DB work) without `asyncio.to_thread`. Changed both to `sync_to_thread=True` synchronous handlers, consistent with every other route that touches the database.

---

## v5.10.1 — RESERVED (zinc-nebula)

**Date:** 2026-03-11
**Status:** Reserved

Do not use this version number (zinc-nebula frontend quality audit in progress).

---

## v5.10.0 — Prompt System, Markdown Rendering & RefineView Redesign

**Date:** 2026-03-10
**Status:** Feature

### Added
- **Markdown rendering in read-only views (ISS-084)** — TranscriptsView preview, TranscribeView ready/viewing panel, and RefineView original panel now render transcript text through `MarkdownBody`, supporting headings, lists, code blocks, tables, and inline formatting.
- **Prompt system backend (ISS-011)** — Migration v9 seeds a system "Prompt" tag and a protected "Default Refinement Prompt" transcript containing the SLM system prompt. Protected transcripts (`is_protected=1`) cannot be deleted via the API or bulk/clear operations.
- **`is_protected` column** on the transcripts table. Protected rows survive `DELETE /api/transcripts`, single-delete, and batch-delete. API returns 403 for attempts to delete a protected transcript.
- **`default_prompt_transcript_id`** field on `RefinementSettings` for future prompt selection persistence.
- **RefineView prompt selector (ISS-081)** — A `<select>` dropdown above the custom instructions textarea lets users pick from any transcript tagged "Prompt". Selecting a prompt pre-fills the instructions field. Selector auto-hides when no Prompt-tagged transcripts exist.

### Changed
- `clear_all_transcripts()` now returns the actual count of deleted rows (excludes protected).
- `transcript_to_dict()` includes `is_protected` in API responses.
- Frontend `Transcript` TypeScript interface includes `is_protected: boolean`.

### Technical Notes
- Migration v9: `ALTER TABLE transcripts ADD COLUMN is_protected INTEGER NOT NULL DEFAULT 0`, seed "Prompt" tag (`is_system=1`), seed default system prompt transcript with `is_protected=1`.
- All delete paths (`delete_transcript`, `batch_delete_transcripts`, `clear_all_transcripts`) append `AND is_protected = 0` / `WHERE is_protected = 0`.
- `MarkdownBody.svelte` (pre-existing) used as-is — no changes to the component itself.
- 14 test assertions updated to account for the seeded protected transcript in fresh databases.

---

## v5.9.5 — Re-Transcribe EditView Polish

**Date:** 2026-03-10
**Status:** Hotfix / Polish

### Changed
- **EditView action bar copy** — Standardized wording to **Re-transcribe** (button label, tooltip, and queued/failure toasts) for consistency with existing TranscribeView/TranscriptsView terminology.
- **EditView analytics control layout** — Swapped control order to text-first then toggle (`Include in analytics` on the left, toggle on the right), matching expected reading/scanning order.
- **ToggleSwitch sizing** — Added a compact `size="sm"` variant and applied it in EditView so the analytics switch is visually less bulky without changing global defaults.

---

## v5.9.4 — Analytics Import Toggle + Re-Transcribe from Cached Audio

**Date:** 2026-03-10
**Status:** Feature

### Added
- **Exclude Imported from Analytics** toggle in Settings → Output tab. When enabled, newly imported audio transcripts are automatically excluded from analytics/usage stats. Existing imports are unaffected.
- **`has_audio_cached` column** on the transcripts table (migration v8). Tracks whether a transcript's source audio WAV is still present in the audio cache.
- **`RetranscribeIntent`** — New intent + handler. Loads cached audio WAV, decodes to int16, and re-runs the full ASR pipeline. Text is updated via `update_normalized_text()`.
- **`POST /api/transcripts/{id}/retranscribe`** endpoint dispatches `RetranscribeIntent`.
- **Re-transcribe button** shown conditionally (when `has_audio_cached` is true) in three locations:
  - **EditView** action bar (left side, beside Discard)
  - **TranscribeView** ready/viewing state (beside Copy)
  - **TranscriptsView** single-select action bar (beside Copy)
- Audio cache eviction now clears `has_audio_cached` on pruned transcripts automatically.
- Stale flag guard: if the cached WAV is missing when re-transcribe fires, the handler clears the flag and emits `transcript_updated`.

### Technical Notes
- `AudioCacheManager.store()` now returns `tuple[Path | None, list[int]]` — the stored path plus IDs of evicted transcripts whose WAVs were pruned.
- `AudioCacheManager.prune()` now returns `list[int]` of evicted transcript IDs (parsed from `{id}.wav` filenames).
- Handler count increased from 26 to 27. Test assertion updated.
- Re-transcription runs on a background thread (same model reuse pattern as import/recording).

---

## v5.9.3 — Audio File Import (ISS-018)

**Date:** 2026-03-10
**Status:** Feature

### Added
- **Import audio files for transcription** — Users can now import pre-recorded audio files (WAV, MP3, M4A, FLAC, OGG, WEBM, WMA, AAC, Opus) via a native OS file dialog. The imported audio runs through the full ASR pipeline: `decode_audio` (ffmpeg) → AudioPipeline (RMS normalization, highpass filter, Silero VAD) → faster-whisper transcription → database storage.
- **"Import Audio File" button** on the TranscribeView idle screen, positioned below the mic controls.
- **Native file picker** via `WindowController.show_open_dialog()` (pywebview `OPEN_DIALOG`), mirrors the existing export save dialog pattern.
- **`ImportAudioFileIntent`** — New intent following the H-pattern. Dispatched by the `/api/import-audio` endpoint after the file dialog returns a path.
- Imported transcripts are automatically tagged with the **"Imported"** system tag and titled with the source filename (without extension).
- Results arrive via the existing `transcription_complete` / `transcription_error` WebSocket events — no new event types needed.

### Technical Notes
- Audio decoding uses `faster_whisper.audio.decode_audio()` (ffmpeg-based, already a dependency). No new packages required.
- Decoding runs on a background thread to keep the API event loop responsive.
- The full AudioPipeline (VAD + normalization) is applied to imported audio — prevents Whisper hallucination on silence-heavy files.
- Handler count in `_register_handlers` increased from 25 to 26. Test `test_handler_count_matches_intent_count` needs its assertion updated (tests/ locked by teal-quasar).

---

## v5.9.2 — Advanced Sampling Settings (ISS-025)

**Date:** 2026-03-10
**Status:** Hotfix / Feature

### Added
- **Advanced sampling parameters in Settings** — The Output tab now exposes Temperature, Top-P, Top-K, and Repetition Penalty behind a collapsible "Advanced Sampling" section. These fields already existed in `RefinementSettings` and were read by `SLMRuntime` at inference time, but were invisible to users. Now they can be tuned from the UI.
  - Temperature (0.01–2.0, default 0.3): controls randomness.
  - Top-P (0.01–1.0, default 0.9): nucleus sampling threshold.
  - Top-K (1–200, default 20): limits token candidates per step.
  - Repetition Penalty (1.0–2.0, default 1.0): penalizes repeated tokens.
- Section is hidden by default (collapsed). Only visible when Grammar Refinement is enabled.
- Uses the same grid layout, input styling, and validation patterns as existing settings controls.

---

## v5.9.0 — Crash-Resilient Audio Recording (ISS-083)

**Date:** 2026-03-10
**Status:** Minor Release

### Added
- **Disk spool during recording** — Audio frames are now incrementally written to a raw PCM spool file on disk as they are captured. If the process crashes, the spool file survives with all audio up to the last ~1-second flush. Spool files live in `<cache_dir>/audio_spool/`.
- **Audio cache with LRU pruning** — After successful transcription, the spool is converted to a standard WAV file in `<cache_dir>/audio_cache/{transcript_id}.wav`. Cache size is bounded by a configurable duration limit (default: 60 minutes, ~115 MB). Oldest recordings are evicted first.
- **`audio_cache_minutes` setting** — New field in Settings → Recording. Controls how much recorded audio to keep on disk (0 = disabled, max 480 minutes). Spool still provides crash safety even when cache is disabled.
- **Startup orphan detection** — On launch, any orphaned `.pcm` spool files (from prior crashes) are logged with duration and path for manual recovery.
- **Navigation lock during recording** — View switching is now blocked while a recording is active, preventing accidental data loss from navigation. Uses the existing `isNavigationLocked` mechanism.

---

## v5.8.9 — Code Quality Pass (cont.)

**Date:** 2026-03-10
**Status:** Hotfix / Maintenance

### Fixed
- **`clearAllTranscripts` wrong response shape** — `DELETE /api/transcripts` returned `{"status": "cleared"}`, but the TypeScript client expected `{"deleted": number}`. `MaintenanceCard` always displayed "Cleared undefined transcripts". Endpoint now counts before clearing and returns `{"deleted": count}`.
- **`EngineStatusData` type gap** — Input-handler degradation events (`{"component": "input", "status": ..., "message": ...}`) were silently dropped by the frontend because `EngineStatusData` only declared `asr` and `slm` fields. Interface and validator extended with the three optional fields.

### Changed
- **Logging style consistency** — One f-string logger call in `application_coordinator.py` converted to `%`-style to match the file's existing convention.
- **Comment cleanup (continued)** — Removed two remaining ISS-ticket annotations from `settings.py` and `SettingsView.svelte`.

---

## v5.8.8 — Code Quality Pass

**Date:** 2026-03-10
**Status:** Hotfix / Maintenance

### Fixed
- **Duplicate dict keys** — `InsightManager._generate_task()` had three keys (`time_saved`, `verbatim_fillers`, `verbatim_filler_density`) silently duplicated in the format dict. Duplicate entries removed; values were identical, so no behaviour change.
- **FTS5 quote escaping** — `TranscriptDB.search()` and `search_count()` stripped inner double-quotes from query tokens instead of doubling them per FTS5 spec. Fixed: `"` → `""`.
- **DELETE 404 on missing transcript** — `DELETE /api/transcripts/{id}` returned HTTP 200 when the transcript did not exist. Now pre-validates existence and returns 404.
- **Stale type: ignore** — Unused `# type: ignore[assignment]` removed from `migrations.py` line 144.
- **Unused imports** — Removed `litestar.response.File` from `api/app.py`, `pathlib.Path` from `log_manager.py`, `flesch_kincaid_grade` from `usage_stats.py`, `typing.Any` from `prompt_builder.py`.

### Changed
- **RecordingOrrery → RecordingPulse** — `RecordingOrrery.svelte` renamed to `RecordingPulse.svelte`; all references updated. The solar-system terminology was vestigial.
- **Comment cleanup** — Removed issue-ticket references, first-person phrasing, and AI-directive capitalisation from inline comments across `refinement_handlers.py`, `transcription_service.py`, `insight_manager.py`, `usage_stats.py`, and `prompt_builder.py` module docstring.

---

## v5.8.7 — Deferred Items Reconciliation

**Date:** 2026-03-10
**Status:** Hotfix / Maintenance

### Changed
- **Deferred items audit** — Reconciled six of seven deferred workboard items. Five closed with no code changes (correctly audited as theoretical or already clean). One fixed.
  - **Inline validation duplication** (fixed): `level` validation moved from duplicated inline checks in `refine_transcript()` and `batch_refine_transcripts()` API handlers into `RefineTranscriptIntent.__post_init__` and `BulkRefineTranscriptsIntent.__post_init__`. API handlers now catch `ValueError` at intent construction. Self-validating intents — validation applies regardless of dispatch origin.
  - **`transcript_to_dict()` location** (closed): audited WebSocket broadcast paths — function is API-layer-only, not used by WS. No move needed.
  - **`system.py` download_model thread** (closed): documented H-pattern exception; thread-safe EventBus emit is correct.
  - **Settings global singleton** (closed): startup order and graceful fallbacks eliminate theoretical risk.
  - **DB None handling audit** (closed): re-confirmed schema `NOT NULL` constraints and dataclass defaults.

### Fixed
- **Stale test assertions** — Handler registration tests updated: added `RevertToRawIntent`, `SetAnalyticsInclusionIntent`, `AppendToTranscriptIntent` to expected intent list; handler count assertion corrected from 23 to 25. Bulk refine `SimpleNamespace` test stubs updated with missing `skip_refined` attribute.

---

## v5.8.6 — Recording UI & Auto-Title Fixes (ISS-082)

**Date:** 2026-03-10
**Status:** Hotfix / Bug Fix

### Fixed
- **ISS-082** — Three post-5.8.5 regressions and a latent bug:
  - **Continue button**: clicking "Continue" in TranscriptsView now auto-starts recording instead of landing on a blank idle screen.
  - **Recording circle double-render**: removed static `background-color` from the mic button so the blob-fill SVG path is the only visible background — the deforming edge and fill now move as one unified shape.
  - **Glow clipping**: changed `overflow: hidden` to `overflow: visible` on the recording display and the wrapping button so the ambient glow radiates freely.
  - **Blob deformation responsiveness**: raised the speaking threshold from 0.01 to 0.05 and made deformation amplitude proportional to the smoothed audio level — the blob now stays still in silence and scales organically with actual speech volume.
  - **Double titling**: when `auto_refine` is enabled the initial post-transcription title generation is now skipped; only the refinement-completion retitle fires, eliminating redundant SLM work.

---

## v5.8.5 — Transcript Continuation / Append (ISS-049)

**Date:** 2026-03-10
**Status:** Patch / Feature

### Added
- **ISS-049** — Recordings can now be appended to an existing transcript instead of always creating a new one. Appended transcripts receive the "Compound" system tag automatically.
  - **TranscriptsView**: single-selected transcript gains a "Continue" action in the action bar — navigates to TranscribeView in append mode targeting that transcript.
  - **TranscribeView (IDLE/RECORDING)**: when in append mode an accent-coloured banner identifies the target transcript; a dismiss button exits append mode without recording.
  - **TranscribeView (READY)**: an "Append to Previous" button appears after transcription completes, merging the new recording into the most recently created other transcript and removing the temporary standalone entry.
  - `append_to_transcript()` DB method: appends new text (with newline separator) to `raw_text` and — if present — `normalized_text`; sums `duration_ms` and `speech_duration_ms`; applies the Compound system tag.
  - `AppendToTranscriptIntent` dispatched via `/api/intents`; `TranscriptHandlers.handle_append` persists and emits `transcript_updated`.
  - v7 DB migration seeds the "Compound" system tag (idempotent).
  - Analytics: compound transcripts count as one session; combined duration and word totals flow through `compute_usage_stats()` unmodified.

---

## v5.8.4 — Analytics Exclusion Controls (ISS-052)

**Date:** 2026-03-10
**Status:** Patch / Feature

### Added
- **ISS-052** — Per-transcript "Include in analytics" toggle in EditView. Mic-sourced transcripts default to included; the flag persists through all downstream analytics.
  - New `include_in_analytics INTEGER NOT NULL DEFAULT 1` column on the `transcripts` table (v6 migration, idempotent).
  - `compute_usage_stats()` filters excluded transcripts before computing any metrics — WPM, word counts, FK grade, filler ratios, radar chart, session stats, and insight generation all respect the flag automatically.
  - `SetAnalyticsInclusionIntent` dispatched via `/api/intents`; `TranscriptHandlers.handle_set_analytics_inclusion` persists to DB and emits `transcript_updated`.
  - EditView: checkbox row below the tag bar, optimistic update with rollback on failure.

---

## v5.8.3 — Bulk Refine Skip-Already-Refined (ISS-078)

**Date:** 2026-03-10
**Status:** Patch / Feature

### Added
- **ISS-078** — Bulk refinement now skips transcripts that already carry the "Refined" system tag by default.
  - Confirmation dialogs for bulk refine include a "Skip already-refined transcripts" checkbox (default: enabled).
  - Backend filters out already-refined IDs before starting the refinement loop; the progress bar total reflects only the transcripts that will actually be processed.
  - If all selected transcripts are already refined and skip is enabled, the operation completes immediately with no work done.
  - `ConfirmOptions` gains optional `checkboxLabel` / `checkboxDefault` fields; `toast.lastCheckboxValue` exposes the result after resolution. All existing confirm callers are unaffected.

---

## v5.8.2 — UI Polish and Interaction Fixes (ISS-080)

**Date:** 2026-03-10
**Status:** Bug Fix / Polish

### Changed
- **ISS-080** — Browser-session UI audit: fixed a batch of visual and interaction issues across TranscribeView, EditView, UserView, and the recording orrery.
  - `TranscribeView`: Session tags label (bookmark icon + "Session tags") now stacks above the tag row instead of sitting inline as a horizontal peer.
  - `RecordingOrrery`: Mic glow clipped with `overflow: hidden` on `.recording-display`; added `blob-fill` SVG path so the dark background correctly tracks blob deformation; definitively resets blob radii and paths to a perfect circle when audio stops.
  - `App.svelte`: Added `min-h-0` to the root flex wrapper, fixing a classic flex overflow bug that caused the nav rail footer (User/Settings) to clip off-screen on content-heavy views.
  - `app.css`: Scrollbar thumb color corrected from near-invisible `--accent-muted` to visible `--blue-5` accent.
  - `EditView`: Added Copy button with clipboard + "Copied" confirm toggle; Discard button restyled to `destructive` variant and repositioned to the far left of the action bar; stats strip centered between two `flex-1` spacers; "grade" metric label capitalized to "Grade".
  - `UserView`: Tab buttons (`Overview` / `Advanced Analytics`) given `cursor-pointer` and `bg-transparent` to match Settings tab affordances.
  - `RadarChart`: All axis label and value text switched to `text-anchor="middle"` for consistent centering; `LABEL_OFFSET` increased from 30 → 46 to give labels clear breathing room from the outer ring.
  - `src/api/app.py`: Replaced Litestar `File` response with plain `Response(bytes)` for both `serve_index` and `serve_mini`, eliminating the `Content-Disposition: attachment` header that caused browsers to download the SPA instead of rendering it.

---

## v5.8.1 — Centralized ActionBar Component (ISS-079)

**Date:** 2026-03-09
**Status:** Maintenance

### Changed
- **ISS-079** — Extracted `ActionBar.svelte` as the single canonical action bar component.
  - Defines the pill-style layout once: `shrink-0` outer wrapper with `px-4 py-2`, stable scrollbar gutter, and a `rounded-lg bg-[var(--surface-secondary)] px-3 py-1.5` inner pill.
  - `TranscriptsView`, `EditView`, and `RefineView` all migrated to use it.
  - Removes the flat `border-t` pattern from EditView and RefineView in favour of the floating pill (consistent with TranscriptsView).
  - Optional `gap` prop (default `gap-2`) for the single case (bulk-refine status bar) that needs wider spacing.

---

## v5.8.0 — UserView Tabbed Layout & Radar Analytics (ISS-035, ISS-037)

**Date:** 2026-03-09
**Status:** Minor Release / Analytics

### Added
- **ISS-035** — UserView now uses a tabbed interface (Overview / Advanced Analytics) to prevent information overload.
  - Overview tab: personalized header, activity heatmap, and new radar chart visualization.
  - Advanced Analytics tab: all original stat cards, distribution charts, and methodology details.
  - Tab state managed in-memory; defaults to Overview.

- **ISS-037** — Custom SVG radar chart displays 6 key speech analytics metrics.
  - Metrics: Speed (WPM), Session Depth (avg duration), Clean Speech (inverse filler %), Activity (transcript count), Vocabulary (FK grade), Time Saved (log minutes).
  - Each metric normalized 0–1 against realistic ceilings (200 WPM, 5-min avg, 15% fillers, 1000 transcripts, grade 12, 1 hour saved).
  - All-time aggregates; fully responsive SVG with concentric scale rings and labeled axes.
  - Zero external chart dependencies—pure Svelte + SVG.

---

## v5.7.1 — UI Polish & Recording Blob Animation (ISS-074, ISS-075, ISS-076, ISS-077)

**Date:** 2026-03-09
**Status:** Visual / UX polish

### Fixed
- **ISS-074** — TranscriptsView action bar: removed top border divider; right edge now aligns with transcript cards via matching `scrollbar-gutter: stable` on an `overflow-y: auto` container.
- **ISS-076** — Global scrollbar stutter mitigation: applied `scrollbar-width: thin` and `scrollbar-color` standard properties as a cross-browser fallback.

### Changed
- **ISS-075** — Scrollbar thumb color changed from gray (`--shell-border`) to blue accent (`--accent-muted` idle, `--accent` on hover). Standard `scrollbar-color` fallback added for non-WebKit browsers. Defined once in `app.css`.
- **ISS-077** — Recording animation overhaul:
  - Removed concentric sonar ripple rings entirely.
  - Replaced with an **amorphous SVG blob** ring that subtly deforms when voice activity is detected.
  - Blob uses 10-point Catmull-Rom spline with RAF-driven random retargeting every ~280ms during speech.
  - Idle state: blob renders as a near-perfect circle with gentle opacity breathing animation (GPU-composited).
  - Mic button border replaced with transparent (blob is the visual ring).
  - Glow radiance response increased: outer glow scale range 0.85→1.65 (was 1.45), box-shadow spread 8→44px (was 32px).
  - Drop-shadow filter on blob SVG provides soft ambient glow without expensive SVG filters.

---

## v5.7.0 — Toast Positioning Overhaul (ISS-047)

**Date:** 2026-03-09
**Status:** Minor Release / Infrastructure

### Changed
- **ISS-047** — Replaced floating toast notifications with a dedicated bottom-strip layout.
  - Toasts now render in a collapsible static strip at the bottom of the window, part of the layout flow.
  - The strip pushes main content upward when active, eliminating z-index conflicts and overlap with action bars.
  - Confirmation dialogs now render inline within the strip (with a backdrop overlay), no longer floating.
  - Empty strip collapses to zero height — no wasted vertical space.
  - Applies consistently across all views: TranscribeView, TranscriptsView, RefineView, EditView, SettingsView, UserView.

---

## v5.6.10 — UserView Silence Metrics Use Measured VAD Data (ISS-073)

**Date:** 2026-03-09
**Status:** Bugfix / Analytics accuracy

### Fixed
- **ISS-073** — UserView "Total Silence" and "Avg. Pauses" metrics now use measured VAD `speech_duration_ms` instead of a word-count heuristic.
  - Previously: silence estimated as `duration − (word_count ÷ 150 WPM × 60)` — a back-of-napkin guess.
  - Now: silence computed as `duration_ms − speech_duration_ms` — actual Whisper VAD timing data.
  - Old transcripts (pre-VAD, `speech_duration_ms = 0`) degrade gracefully: silence = full duration.
  - Explanation text updated to reflect the new calculation method.
  - Aligns UserView with backend sorting, which already uses `duration_ms − speech_duration_ms`.

---

## v5.6.9 — EditView Metrics & Session Tag Tooltip (ISS-063, ISS-064, ISS-069)

**Date:** 2026-03-09
**Status:** Enhancement / UX

### Changed
- **ISS-063** — EditView stats strip expanded with three new metrics.
  - **Active Speech %**: Shows ratio of speech to total recording duration (when VAD data available).
  - **Reading level**: Flesch-Kincaid grade level computed from the current editor text (requires ≥3 words).
  - **Filler density**: Filler count now includes percentage of total words (e.g., "3 fillers (1.2%)").

### Added
- **ISS-069** — Session tags bar now has a tooltip explaining that selected tags are auto-applied to every new recording until cleared.

### Internal
- **ISS-064** — Analytics rationalization audit completed. All displayed metrics across EditView, TranscribeView, and UserView reviewed. Keep/remove recommendations produced. Silence-estimation metrics in UserView (Total Silence, Avg. Pauses) flagged as imprecise — they use estimated speech time from word count rather than measured VAD data.

---

## v5.6.8 — MOTD Enrichment & Orrery Performance (ISS-070, ISS-071)

**Date:** 2026-03-09
**Status:** Hotfix / Enhancement

### Changed
- **ISS-070** — TranscribeView greeting/MOTD now uses richer data context for more varied, dynamic output.
  - MOTD prompt receives 11 data points (up from 4): filler count/density, refinement count, time saved, today's session count/words, days active this week.
  - `compute_usage_stats` now computes per-day session metrics (`today_count`, `today_words`, `days_active_this_week`).
  - MOTD allowed to be 1–3 sentences (up from a strict 15-word one-liner).
  - Prompt rewritten with more varied examples and angle-switching guidance.

### Fixed
- **ISS-071** — Recording orrery animation stutter at full 4K resolved.
  - Replaced `box-shadow` keyframe animation (triggers full repaint) with an opacity-animated `::after` pseudo-element (GPU-composited).
  - Added `will-change: transform, opacity` and `translateZ(0)` GPU layer promotion to ripple rings.
  - All animation keyframes now use `translate3d` for consistent compositor-layer handling.

---

## v5.6.7 — Model Maintenance & Restart Toast (ISS-061, ISS-062)

**Date:** 2026-03-09
**Status:** Hotfix / Maintenance

### Changed
- **ISS-062** — Dropped sub-4B SLM model support. The Qwen3 1.7B model has been removed from the registry; Qwen3 4B is now the smallest selectable refinement model.
  - Existing installations configured for 1.7B automatically fall back to the smallest remaining model on next startup.
  - Qwen3 4B tier relabelled from "balanced" to "fast".

### Added
- **ISS-061** — Model-change toast now informs the user a restart is required. When either the ASR or SLM model is changed and settings are saved, the toast reads: "Model change saved. Go to Maintenance → Restart Engine to apply."

---

## v5.6.6 — UI Bug Fixes (ISS-056, ISS-057, ISS-058, ISS-059, ISS-060)

**Date:** 2026-03-09
**Status:** Hotfix / Bug Fix

### Fixed
- **ISS-056** — "Your Name" and "Typing Speed (WPM)" fields were mis-filed in the Recording tab. Both are user identity/preference settings with no relation to recording behaviour. Moved to the Appearance tab.
- **ISS-057** — Action bar background in TranscriptsView bled edge-to-edge while transcript cards have `rounded-lg` insets, creating a visual shelf. Both action bar variants (selection and bulk-refine progress) now wrap their content in a `rounded-lg` inner div that aligns with card edges.
- **ISS-058** — Recording status bar (Cancel button, pulse indicator, timer) was rendered inside `RecordingControls` and got vertically centred with the mic button. Extracted from `RecordingControls` and placed in `TranscribeView` below `<WorkspacePanel>`, matching the position of action bars for all other view states. `formatElapsed` extracted to `formatters.ts`.
- **ISS-059** — Session tags strip in TranscribeView was left-aligned. Added `justify-center` to horizontally centre tag content with the rest of the view.
- **ISS-060** — Transcript rename was unimplemented in EditView despite backend endpoint and intent existing. Added `renameTranscript()` to `api.ts`. EditView header title is now click-to-edit: clicking shows an inline input with confirm (Enter/blur) and cancel (Esc) behaviour.

---

## v5.6.5 — Bulk Refine Route Fix (ISS-055)

**Date:** 2026-03-09
**Status:** Hotfix / Bug Fix

### Fixed
- **ISS-055** — `batch_refine_transcripts` and `cancel_batch_refine` handlers were defined in `transcripts.py` but never imported into `app.py` or added to `route_handlers`. Every bulk-refine attempt returned HTTP 405 Method Not Allowed. Both handlers now registered correctly.

---

## v5.6.4 — UI Reactivity Fix (ISS-065)

**Date:** 2026-03-09
**Status:** Hotfix / Bug Fix

### Fixed
- **ISS-065** — localStorage unavailable in pywebview's WebKitGTK context crashed Svelte's effect scheduler.
  - TranscribeView's session tag persistence $effect threw on mount, breaking all downstream reactivity (navigation, animations, rendering).
  - Wrapped localStorage access with try/catch to gracefully degrade when unavailable.
- Missing WebSocket event validators for bulk refinement events (v5.6.3 regression).
  - Added validators for `bulk_refinement_started`, `bulk_refinement_progress`, `bulk_refinement_complete`, `bulk_refinement_error` to prevent type errors.

---

## v5.6.3 — Bulk Refinement (ISS-020)

**Date:** 2026-03-09
**Status:** Hotfix / Feature

### Added
- **ISS-020** — Bulk refinement of transcripts from TranscriptsView.
  - Multi-select transcripts and click "Refine N" in the action bar to queue sequential SLM refinement.
  - Spot-check safety gate: for batches larger than 10, a confirmation dialog offers to refine the first 10 before proceeding with the full set.
  - Auto-commit: each transcript is refined, persisted, and tagged "Refined" automatically — no manual accept step.
  - Progress bar with live count in the action bar during processing.
  - Cancel support: stop between transcripts without losing already-committed work.
  - Errors on individual transcripts are skipped without aborting the batch.
  - Auto-retitle fires per transcript if enabled in settings.
  - Backend: `BulkRefineTranscriptsIntent`, `CancelBulkRefinementIntent`, `POST /api/transcripts/batch-refine`, `POST /api/transcripts/batch-refine/cancel`.
  - WebSocket events: `bulk_refinement_started`, `bulk_refinement_progress`, `bulk_refinement_complete`, `bulk_refinement_error`.
  - Single-transcript refine blocked while bulk is in progress (and vice versa).

---

## v5.6.2 — Session Auto-Tagging (ISS-046)

**Date:** 2026-03-09
**Status:** Hotfix / Feature

### Added
- **ISS-046** — Session auto-tagging in TranscribeView: a persistent tag selector (using the existing `TagBar` component) appears between the header stats and the workspace panel during idle and recording states.
  - Selected session tags are automatically assigned to every new transcript when `transcription_complete` fires.
  - Session tag selection persists across app restarts via `localStorage`.
  - A post-transcription confirmation strip below the workspace panel lists the tags that were auto-applied after each recording.
  - Deleting a tag from the context menu also removes it from the active session tag set.
  - System tags are excluded from the session tag selector (they should never be manually pinned).

---

## v5.6.1 — TranscriptsView Action Bar Alignment (ISS-054)

**Date:** 2026-03-09
**Status:** Hotfix / Bug Fix

### Fixed
- **ISS-054** — TranscriptsView action bar padding now visually aligns with transcript list content edges by adding `scrollbar-gutter: stable` to the action bar container. The scroll container and action bar both reserve space for the scrollbar, eliminating the ~15px left-shift misalignment that occurred when the scrollbar was present.

---

## v5.6.0 — EditView Redesign (ISS-045)

**Date:** 2026-03-09
**Status:** Minor Release

### Added
- **ISS-045** — EditView redesign: tags panel, statistics strip (word count, duration, WPM, filler count), Refined status banner with revert-to-raw button, and full tag management.
- **TagBar.svelte** — Extracted reusable tag chip bar component from TranscriptsView. Renders tag chips (system tag awareness), inline creation form, and right-click context menu (color picker + delete). Used by TranscriptsView (filter mode) and EditView (assignment mode). Ready for TranscribeView (ISS-046).
- **RevertToRawIntent** — New backend intent that clears `normalized_text` and removes the Refined system tag, restoring original captured text. Wired through CommandBus, intent dispatch API, and coordinator.
- **Toast positioning fix** — Moved toast stack from `fixed bottom-4 right-4` to `fixed top-12 right-4`, eliminating overlap with RefineView action bar buttons. Partial fix for ISS-047.

### Changed
- **TranscriptsView** — Tag filter chips, inline creation, and context menu replaced with shared TagBar component. Removed ~100 lines of inline tag management code.
- **EditView** — Complete rewrite from bare textarea (160 lines) to full-featured editor (~270 lines) with tag management, statistics, Refined indicator, and revert capability.

---

## v5.5.1 — Code-Level TODO Sweep

**Date:** 2026-03-09
**Status:** Hotfix / Polish

### Changed
- **RecordingControls extraction** — Extracted mic button, orrery visualizer, cancel bar, and recording timer into a new `RecordingControls.svelte` component. TranscribeView delegates via props and callbacks, reducing its line count significantly.
- **Chord logic extraction** — `make_capture_handler()` moved to `src/input_handler/key_capture.py`. The `start_key_capture` route handler is now a thin wrapper that passes an `on_chord` callback.
- **Evdev keyboard hotplug** — `EvdevBackend._rescan_devices()` runs every 3 s inside the listen loop, diffs `/dev/input/*` paths, and opens newly connected key-capable devices without requiring a restart.
- **Mic device-loss detection** — `AudioService` now accepts an `on_device_lost` callback. Sustained `input_overflow` flags (10+ consecutive callbacks) and `PortAudioError` exceptions during recording both fire the callback for proactive notification.
- **Input backend degradation event** — `KeyListener._log_backend_limitations()` now fires an `on_degradation` callback (wired via `create_listener`), which the coordinator emits as an `engine_status` WebSocket event so the frontend can surface a toast.

---

## v5.5.0 — Refined System Tag (ISS-044)

**Date:** 2026-03-09
**Status:** Minor Release

### Added
- **ISS-044** — "Refined" system tag: auto-applied to a transcript when refinement is committed.
  - DB migration v5: `is_system` column added to `tags` table; "Refined" system tag seeded on first run / upgrade.
  - `CommitRefinement` handler applies the Refined tag to the transcript and emits `transcript_updated` so TranscriptsView refreshes live.
  - System tags cannot be edited, deleted, or manually assigned by the user — enforced at the handler, DB, and API levels.
  - `assign_tags` now preserves system tags when a user changes their tag selection (no longer wipes auto-applied tags).
  - Frontend: system tags render with a `Hammer` icon instead of a color dot in all tag surfaces (filter strip, transcript cards).
  - Frontend: system tags are excluded from the tag assignment popover and the right-click edit/delete context menu.
  - `remove_system_tag_from_transcript` DB method added (for the ISS-045 revert-to-raw flow).

---

## v5.4.5 — Username Greeting, VAD Preload, Auto-Refine (ISS-050, ISS-048, ISS-051)

**Date:** 2026-03-09
**Status:** Feature

### Added
- **ISS-050** — Username greeting personalization.
  - Greeting in TranscribeView now includes the user’s name if set: “Good afternoon, Drew!”
  - New “Your Name” text input in Settings → Recording tab. Reads from existing `user.name` field.
  - Greeting updates live when settings change (via `config_updated` WebSocket event).
- **ISS-051** — Auto-refine toggle.
  - New “Auto-Refine After Recording” toggle in Settings → Output tab.
  - When enabled, each transcription is automatically refined at the default level and committed without user intervention.
  - Listens for `refinement_complete` WebSocket event and auto-commits the result.
  - New `output.auto_refine` boolean in settings (default: false).
- **ISS-048** — Silero VAD model preloaded at startup.
  - VAD ONNX model now loads during application startup (after ASR model), eliminating cold-start latency on first transcription.
  - New `RecordingSession.load_vad_model()` method follows the same pattern as `load_asr_model()`.

### Changed
- **TranscribeView** — Stats strip redesigned as a card with title-case labels above numbers, surface-secondary background, and vertical dividers.
- **TranscribeView** — Greeting now always ends with “!” even without a username set.
- **TranscriptsView** — Card list uses `scrollbar-gutter: stable` to prevent content shift when scrollbar appears.

---

## v5.4.3 — ActivityHeatmap Layout Polish

**Date:** 2026-03-09
**Status:** Hotfix / Polish

### Changed
- **ActivityHeatmap** — Timescale toggle moved from bottom bar to title row, abbreviated as M/Q/Y single-letter buttons.
- **ActivityHeatmap** — Month labels (Jan/Feb/Mar...) now rendered at `text-[var(--text-primary)] font-medium` for visual prominence, up from unstyled secondary color.
- **ActivityHeatmap** — Month label row height increased (22→30px), `items-end` changed to `items-center` — eliminates the cramped gap between month name and grid top.
- **ActivityHeatmap** — Bottom area split into two rows: stats line (left-aligned with grid) and legend row (centered), replacing the crowded three-element single row.

---

## v5.4.2 — Toast & Confirmation System (ISS-026)

**Date:** 2026-03-09
**Status:** Feature

### Added
- **Toast confirm() API** — `toast.confirm({ title, message, confirmLabel?, cancelLabel?, danger? })` returns a `Promise<boolean>`. One confirmation dialog shown at a time with FIFO queue. Esc/backdrop click cancels, Enter confirms.
- **Confirmation dialog UI** — modal card with backdrop, danger variant support, keyboard handling. Uses existing `StyledButton` and design token system.
- **`animate-fade-in`** CSS keyframe for backdrop transitions.

### Changed
- **RefineView** — `handleAccept()` now has proper try/catch (was silently swallowing errors). Toast success on refinement complete, toast error on refinement failure and commit failure.
- **TranscriptsView** — Toast feedback on delete (single + batch), tag create, tag delete, tag color change failure, and tag assignment failure.
- **EditView** — Toast error on save failure, toast success on save.
- **SettingsView** — Toast success/error alongside existing inline message system.
- **UserView** — Toast error on insight refresh failure.

---

## v5.4.1 — Recording Active State UX Overhaul

**Date:** 2026-03-09
**Status:** Hotfix / Polish

### Changed
- **RecordingOrrery** — the mic button in the recording state is now a fixed 160 px circle, matching the idle mic button exactly. Both states use the same visual footprint for a seamless transition.
- **Stop interaction** — the large central orrery button is now clickable and stops the recording. The redundant "Stop & Transcribe" button in the control bar has been removed.
- **Control bar** — "Recording in progress…" text is now centered; the elapsed timer moves to the far right (occupying the space vacated by the stop button); the divider between them is removed.
- **RecordingOrrery** — mic icon size now scales proportionally with the circle diameter (35% of `micSizePx`, matching the idle button's icon-to-circle ratio).

---

## v5.4.0 — Inference Quantization + Decoding Optimization (ISS-042, ISS-043)

**Date:** 2026-03-09
**Status:** Minor Release

### Changed
- **ISS-042** — Explicit `compute_type` for Whisper and SLM inference engines.
  - Added `compute_type` setting to `ModelSettings` (default: `"int8"`).
  - WhisperModel and ctranslate2.Generator now receive explicit quantization.
- **ISS-043** — Greedy decoding for SLM refinement.
  - Added `beam_size=1` to both `generate_batch()` calls in the refinement engine.

---

## v5.3.13 — Refinement Generation Params Into Settings (TODO-4)

**Date:** 2026-03-09
**Status:** Hotfix / Polish

### Changed
- **TODO-4** — `temperature`, `top_p`, `top_k`, and `repetition_penalty` are now stored in `RefinementSettings` instead of being scattered as hardcoded literals.
  - `RefinementSettings` gains four fields with the previously-hardcoded production defaults (`temperature=0.3`, `top_p=0.9`, `top_k=20`, `repetition_penalty=1.0`).
  - `SLMRuntime._sampling_params_for_level()` reads from live settings instead of returning a static dict; method changed from `@staticmethod` to instance method.
  - `RefinementEngine.refine()` gains `repetition_penalty` as an explicit parameter (was hardcoded in the `generate_batch()` call body and not overridable by callers).
  - Defaults on `engine.refine()` updated to match the production values (`temperature` was 0.05, `top_p` was 0.8 — both stale from an earlier tuning era).
  - Lays groundwork for ISS-025 (advanced model settings UI) without touching the API or frontend.

---

## v5.3.12 — Retire Show Backend Details (ISS-041)

**Date:** 2026-03-09
**Status:** Hotfix / Polish

### Removed
- **Show/Hide backend details** toggle removed from the GPU Status row in Settings → Speech Recognition.
  - The whisper.cpp-era `whisper_backends` capability-flag string (`AVX = 1 | CUDA = 1 | …`) was replaced in v5.0 by a plain CTranslate2 description string. The old flag parser produced zero results on every machine. The GPU name badge already conveys all useful information.
  - `whisper_backends` field removed from `GpuInfo` in `api.ts`, `AsrModelCard` props, `SettingsView` type annotation, and the `_detect_gpu_status()` backend function.

---

## v5.3.11 — EmptyState Component Extraction (ISS-040)

**Date:** 2026-03-09
**Status:** Hotfix / Polish

### Changed
- **ISS-040** — Extracted a shared `EmptyState` component, eliminating eight copy-pasted idle/loading/error placeholder patterns across three views.
  - **`EmptyState.svelte`**: new component supporting an optional Lucide icon, message string, fixed or full height, spinning animation, and a `children` snippet slot for complex inline content.
  - **`RefineView`**: select-transcript idle, refining spinner, refinement error, and ready-to-refine waiting states ported to `EmptyState`.
  - **`SettingsView`**: settings-loading spinner ported to `EmptyState`.
  - **`TranscriptsView`**: transcript-list loading, error, and empty-filtered-list states ported to `EmptyState`.
  - **Button and panel audits**: all 26 raw `<button>` elements individually reviewed; every one is structurally specialized (hero mic button, tag pills, menu items, tab controls, etc.) — none converted. `WorkspacePanel` adoption audit confirmed it is already correctly scoped.

---

## v5.3.10 — Transcriptions Width Constraint + Refinement Test Contract Fix (ISS-039)

**Date:** 2026-03-09
**Status:** Hotfix / Polish

### Changed
- **ISS-039** — Transcriptions view now uses a single centered content wrapper capped at 80% width on desktop.
  - **Shared width reference**: search header, controls row, transcript cards, and bottom action bar now align to the same container instead of each row stretching edge to edge independently.
  - **Responsive behavior preserved**: smaller viewports still use the available width, so this avoids the fullscreen sprawl without introducing cramped mobile nonsense.

### Fixed
- **ISS-032 test artifact** — `test_successful_refinement_updates_text_and_emits` was asserting the old pre-ISS-032 behavior where refinement completion immediately wrote to the database.
  - Renamed and corrected the test to assert the actual contract: refinement completion emits preview text without persisting it.
  - Added explicit coverage for the commit path so `handle_commit_refinement()` is the only thing asserting persistence of accepted refinement text.

---

## v5.3.9 — Settings Tabbed Redesign + Scroll Fix (ISS-038)

**Date:** 2026-03-09
**Status:** Hotfix / Polish

### Changed
- **ISS-038** — Settings view rebuilt with a horizontal tab bar replacing the stacked-card layout.
  - **Tab bar**: five tabs (Speech Recognition, Recording, Output, Appearance, Maintenance) with lucide icons. Active tab indicated by accent underline and color change. Tab bar is sticky so it remains visible while scrolling long sections.
  - **Card chrome stripped**: outer wrapper divs and header rows removed from `AsrModelCard`, `OutputCard`, and `MaintenanceCard`. The tab header replaces the need for per-card section titles.
  - **Centering fix**: tab bar moved inside the `overflow-y-auto` scroll container as `sticky top-0`. Root cause: when the tab bar lived outside the scroll area, a visible scrollbar reduced the scroll container width by ~15 px, shifting `mx-auto` content left while the tab bar stayed centered at full width. Both now reference the same parent width.
  - **Maintenance layout**: Transcriptions and Engine cards changed from single-column to side-by-side (`grid-cols-2`).

### Fixed
- **Scroll throttling** — `overflow-hidden` → `overflow-clip` on the flex-row and `<main>` wrappers in `App.svelte`. `clip` prevents visual overflow identically but does not create a scroll container, eliminating the scroll geometry conflict that caused mouse-wheel fighting in Settings and UserView.

---

## v5.3.8 — Settings View Overhaul (ISS-006)

**Date:** 2026-03-08
**Status:** Hotfix / Polish

### Changed
- **ISS-006** — Settings view overhaul addressing six sub-items of accumulated UX debt.
  - **Max-width constraint**: content wrapper now uses `max-w-6xl` matching UserView, preventing edge-to-edge stretch at fullscreen.
  - **Help text → tooltips**: all inline italic description paragraphs converted to `title` attributes on their labels. Dramatic reduction in visual noise.
  - **Font-size hierarchy**: labels promoted from `text-base text-secondary` to `text-sm text-primary`, creating clear dominance over controls. Grid rows use `items-center` instead of `items-start` for tighter alignment.
  - **Status bar removed**: the "Online · v5.0.0 · 259 transcripts" bar at the top of Settings added little value and displayed stale data; removed entirely.
  - **Export section cleanup**: shortened button labels ("Export" / "Clear All"), removed inline help text, removed uppercase micro-labels, tightened spacing.
  - **Grid alignment**: consistent `items-center` alignment across all setting cards (SettingsView, AsrModelCard, OutputCard). Controls sit on the same baseline as their labels.

---

## v5.3.7 — Activity Heatmap Timescale Controls (ISS-034)

**Date:** 2026-03-08
**Status:** Hotfix / Feature

### Added
- **ISS-034** — Month / Quarter / Year timescale toggle on the activity heatmap.
  - Three compact toggle buttons (Month, Quarter, Year) sit in the legend row between the stats text and the color legend.
  - **Year** (default): all 12 months of the current year. When months must be trimmed for narrow containers, the trim is now centered on the current month rather than always removing from January (auto-center).
  - **Quarter**: current month ±1 (3-month window); wraps year boundaries.
  - **Month**: current month only.
  - Cell size scales up to fill available width in all views.

---

## v5.3.6 — Retire "Retitle All Untitled" (ISS-036)

**Date:** 2026-03-08
**Status:** Hotfix / Cleanup

### Changed
- **ISS-036** — "Retitle All Untitled" feature retired. DB query confirmed only 2 untitled transcripts remain out of 259; all new transcripts are auto-titled on creation.
  - Removed: `BatchRetitleIntent`, `TitleGenerator.batch_retitle()` / `_batch_retitle_task()`, `TitleHandlers.handle_batch_retitle()`, `TranscriptDB.get_untitled_transcripts()`, `batchRetitle()` API function, `BatchRetitleProgressData` event type, "Titles" card in MaintenanceCard.
  - Handler count in coordinator updated from 19 (stale) to 20 (accurate — includes `CommitRefinementIntent` and `BatchToggleTagIntent` from ISS-030/032).

---

## v5.3.5 — Bulk Tag Toggle (ISS-030)

**Date:** 2026-03-08
**Status:** Hotfix / Bug Fix

### Fixed
- **ISS-030** — Multi-select tag assignment completely reworked.
  - **O(n) loop eliminated**: new `POST /api/transcripts/batch-tag-toggle` endpoint dispatches `BatchToggleTagIntent`, which calls `db.batch_toggle_tag()` — a single `executemany` transaction instead of one request per transcript.
  - **Tag replacement bug fixed**: clicking a tag in multi-select now adds it to transcripts that lack it (or removes it from all if every selected transcript already has it). All other tags on each transcript are untouched.
  - **Checkmarks in multi-select**: ✓ shown when ALL selected transcripts have the tag; — (dash) shown when only SOME have it; blank when none have it.

---

## v5.3.4 — MOTD Clip Fix + Transcriptions Action Bar

**Date:** 2026-03-08
**Status:** Hotfix / Polish

### Fixed
- **ISS-028** — MOTD insight paragraph in TranscribeView now has `max-w-prose`, horizontal padding, and `overflow-wrap: anywhere`. Text wraps cleanly at any viewport width instead of clipping at the edge.
- **ISS-029** — Transcriptions action bar overhauled: selection count moved to the controls row (right of total transcript count); Delete left-aligned; Edit / Copy / Tag / Refine right-aligned; Refine promoted to `variant="primary"` (accent blue); raw `<button>` Clear removed (Escape clears selection).

---

## v5.3.3 — Version Resolution Fix + UserView Width

**Date:** 2026-03-08
**Status:** Hotfix / Polish

### Fixed
- **ISS-027** — `_resolve_app_version()` now reads `pyproject.toml` first and falls back to `importlib.metadata`. The stale installed metadata no longer causes a wrong version in the UI. Coordinator startup log now uses `APP_VERSION` instead of the hardcoded `"v5.0..."` string.
- **ISS-033** — UserView content width bumped from `max-w-4xl` (896 px) to `max-w-6xl` (1152 px), filling roughly half a 1920 px viewport at fullscreen.

---

## v5.3.2 — Refinement Accept/Discard + Button Bar Polish

**Date:** 2026-03-08
**Status:** Hotfix / UX

### Overview

Fixed a content-preservation bug where the refinement backend silently overwrote `normalized_text` the moment inference completed — before the user ever saw or approved the result. Refinement is now a two-phase operation: the backend emits the result over WebSocket, and the database is only written when the user explicitly clicks **Accept & Copy**. Discarding a result is now a genuine no-op.

Also cleaned up the RefineView action bar to match the project's design system.

### Fixed
- **ISS-032** — Refinement no longer writes `normalized_text` to the database until the user accepts the result. "Discard Result" is now a true discard — the original text is fully preserved.
- **ISS-031** — RefineView action bar: "Accept & Copy" converted from raw `<button>` to `StyledButton`; destructive action (Discard) left-aligned, positive action (Accept) right-aligned; "Delete Result" renamed to "Discard Result" with accurate tooltip.

### Changed
- `refinement_handlers.py` — `do_refine()` no longer calls `db.update_normalized_text()`. Auto-retitle on refine is now triggered from the commit path, not the inference path.
- New `CommitRefinementIntent(transcript_id, text)` intent and `handle_commit_refinement()` handler persist the accepted text and trigger auto-retitle if enabled.
- New endpoint `POST /api/transcripts/{id}/refine/commit` dispatches the commit intent.
- `handleAccept()` in `RefineView.svelte` awaits the commit API call and updates the Original panel to reflect the newly accepted text.

---

## v5.3.1 — Recording View Polish: Audio-Reactive Mic Button

**Date:** 2026-03-08
**Status:** Polish / Cleanup

### Overview

Scrapped the over-engineered canvas-based solar system orrery (221MB pre-rendered sprite atlases, three TypeScript modules, an offline Node.js pre-render pipeline) that failed to render reliably under WebKitGTK. Replaced with a focused, ~100-line audio-reactive mic button that does exactly what the recording view needs: a centered indicator that pulses with your voice.

### Removed
- `frontend/src/lib/orrery/` — `aurelia-system.ts`, `renderer.ts`, `atlas-loader.ts` (1,500+ lines of canvas/sprite machinery)
- `scripts/prerender-orrery/index.ts` — offline Node.js pre-render pipeline
- `@napi-rs/canvas` devDependency and `prerender:low/medium/high` npm scripts
- `planet_density` field from `DisplaySettings`, all frontend config/WS handlers, and the "Planet Density" dropdown in `SettingsView`

### Changed
- **`RecordingOrrery.svelte`** — Rewritten from 267 lines of broken canvas machinery to ~100 lines of clean DOM:
  - Audio-reactive radial glow: `scale` and `opacity` track `audioLevel` via a smoothed rAF loop
  - `box-shadow` on the mic button brightens proportionally with voice amplitude
  - Two staggered sonar-style ripple rings (4.5s expand-and-fade, active only while speaking)
  - Idle breathing animation (`@keyframes`) when silent, disabled via `animation: none` when the rAF loop is active so CSS never overrides JS-driven values
  - Responsive sizing via `ResizeObserver`

---

## v5.3.0 — Database Schema Simplification & Legacy System Removal

**Date:** 2026-03-07
**Status:** Feature / Refactor

### Overview

Massive architectural cleanup removing the deprecated "Project" and "Variant" systems.

### Architectural Changes
- **Variant System Removed**: Dropped the concept of transcript variants. The `Transcript` model now stores the final text directly in `normalized_text`. 
- **Project System Removed**: All remnants of the legacy "Project" feature were thoroughly expunged from the database, API, and UI.

### Database & API
- **v4 Database Migration**: Implemented a comprehensive SQLite migration to safely collapse variant rows directly into the `normalized_text` field of `transcripts` before dropping deprecated columns and tables.
- **Simplified Intents**: Removed `DeleteTranscriptVariantIntent` and optimized handling of SLM refinement events to update `normalized_text` in-place, dramatically simplifying the persistence layer.

### Tests
- Audited and updated over 540 unit and integration tests to align with the strictly normalized database schema.

---

## v5.2.2 — Frontend Audit: Dead Code, Component Consolidation, Design Conformity

**Date:** 2026-03-07
**Status:** Maintenance Release (no behavior change)

### Overview

Comprehensive frontend audit pass. Removed dead/orphaned code, consolidated duplicate implementations, enforced Svelte 5 idioms, centralised global animations, and applied design-system conformity across all action bars.

### Dead / Orphaned Code Removed
- **`ws.on("refinement_error", () => {})`** — no-op WebSocket subscription in `TranscriptsView` doing literally nothing. Deleted.
- **`monstercat` prop** — legacy alias for `spreadFactor` in `BarSpectrumVisualizer`. Removed from Props interface and destructuring.
- **Local `formatCount()`** — identical one-liner duplicated in `UserView` and `ActivityChart`. Centralised in `formatters.ts`; both files now import it.

### Deprecated API Fixed
- **`<svelte:component this={...}>`** in `ToastContainer` — Svelte 4 syntax. Replaced with Svelte 5 `{@const Icon = iconMap[...]}` pattern.

### Bespoke Reimplementations Replaced
- **Bespoke border-div spinner** in `UserView` — replaced with `<Loader2 class="spin" />` consistent with every other view.
- **Hand-rolled save bar buttons** in `SettingsView` — 200-char inline Tailwind strings replaced with `<StyledButton variant="ghost/primary" size="sm">`. `StyledButton` imported.
- **Hand-rolled recording bar buttons** in `TranscribeView` (Cancel, Stop & Transcribe) — replaced with `StyledButton`.
- **Three hand-rolled action buttons** in `RefineView` (Re-run, Delete Result, Refine) — replaced with `StyledButton`. `StyledButton` imported.

### Component Library Extended
- **`StyledButton`** — added three new semantic variants: `danger-outline` (outline danger, soft fill on hover), `neutral` (shell border, accent border on hover), `danger-reveal` (shell border that floods danger on hover). Added `title` and `ariaLabel` prop passthrough. Removed spurious `border-none` from base class (each border-free variant now carries it explicitly).
- **`DownloadButton.svelte`** — new shared component. Extracted identical ghost-outline-accent download button that was copy-pasted verbatim between `AsrModelCard` and `OutputCard`. Both updated to use it.

### Global Animations Centralised
- Moved `@keyframes spin` + `.spin` class from `TranscribeView` `<style>` block to `app.css`.
- Moved `@keyframes pulse-dot` from `TitleBar` and `TranscribeView` `<style>` blocks (duplicated in both) to `app.css`.
- Moved `@keyframes slide-in` + `.animate-slide-in` from `ToastContainer` `<style>` block to `app.css`.
- All three component `<style>` blocks removed entirely.

### Stale Historical Comments Removed
- Removed "Ported from PyQt6 …" header comment from `app.css`.
- Removed PyQt6 docblock references from `WorkspacePanel`, `ToggleSwitch`, and `SettingsView`.

### Design Principle Enforcement (Destroy-Left / Create-Right)
- **`RefineView`** action bar: `[Accept & Copy] [Re-run] [Delete Result]` → `[Delete Result] [Re-run] [Accept & Copy]`.
- **`TranscriptsView`** selection bar: `[N selected] … [Clear] [Delete]` → `[Delete] [N selected] … [Clear]`.

---

## v5.2.1 — Python Backend Style Pass

**Date:** 2026-03-07
**Status:** Maintenance Release (no behavior change)

### Overview

PEP 8 compliance and naming clarity pass across all backend Python files. No logic changed.

### Changed

- **Naming** — Replaced ambiguous single-letter variables throughout: `t` → `transcript` (Transcript objects), `t` → `token` (FTS search tokens), `t` → `thread` (Thread objects), `m`/`h`/`rm` → `minutes`/`hours`/`remaining_minutes` in `InsightManager._fmt_duration`, `s` → `settings` in `SLMRuntime` and `LogManager`.
- **Import hygiene** — `from abc import ABC` moved before `from dataclasses import dataclass` in `intents/__init__.py` (stdlib alphabetical order); `import time` moved from inside `_batch_retitle_task` method body to module-level in `title_generator.py`; removed empty `if TYPE_CHECKING: pass` block in `log_manager.py`.
- **Redundant code** — Removed `pass` from `InteractionIntent` body (docstring makes it unnecessary).
- **Type annotation** — Added `-> None` return type to `PluginLoader.discover_plugins`.
- **Logging style** — Converted f-string logging calls to `%s`-style (deferred formatting) in `plugins/loader.py`, `log_manager.py`, and `input_handler/listener.py` for consistency with the rest of the codebase.
- **Unused parameters** — `x, y` → `_x, _y` in `PynputBackend._on_mouse_click` (coordinates required by pynput's callback signature but never read).

---

## v5.2.0 — Transcriptions View Overhaul (ISS-015)

**Date:** 2026-03-07
**Status:** Feature Release

### Overview

Complete redesign of the Transcriptions view. Ships server-side pagination and multi-column sorting, a rebuilt search bar, a dedicated EditView, tag management improvements, and a full card UI refresh with relative timestamps and improved typography.

### Added

- **Server-side pagination** — `db.recent()` now accepts `limit`, `offset`, and `sort_by` parameters. API returns `{items, total}` envelope. Frontend renders prev/next navigation with configurable page sizes (10 / 25 / 50).
- **Multi-column sort** — Sort by: Newest, Oldest, Longest, Shortest, Most Words, Fewest Words, Most Silence, Least Silence. `_SORT_EXPRESSIONS` dict in `db.py` maps virtual keys to SQL expressions; silence computed as `duration_ms - speech_duration_ms`.
- **Dedicated `EditView.svelte`** — Focused, single-purpose transcript editing surface. No recording machinery. Full-height layout: header (title + metadata + tags), textarea, footer (word count + dirty indicator + Save/Discard). `Ctrl+S` saves; `Escape` discards. Navigated to via `nav.navigateToEdit()`; returns to origin on save/discard.
- **Tag right-click context menu** — Right-clicking any tag chip opens a positioned popover with an inline color picker and a Delete action. Replaces the broken `confirm()` dialog approach. `onpointerdown|stopPropagation` prevents the global handler race that caused the earlier delete failure.
- **Tag color editing** — Color picker in the tag context menu calls `updateTag(id, {color})` via the existing REST endpoint. Live color update with no page reload.
- **`formatRelativeDate()`** in `formatters.ts` — Produces human-readable relative dates: "just now", "14m ago", "6h ago", "Yesterday 3:07 PM", "Mon 3:07 PM" (this week), "Mar 7" (this year), "Mar 7, 2025" (older).

### Changed

- **`ViewId`** in `navigation.svelte.ts` — Added `"edit"` variant. `navigateToEdit()` now routes to the new EditView instead of TranscribeView's internal edit mode.
- **`formatDuration()`** — Recordings ≥ 10 min now drop seconds ("22m" not "22m 19s"). Sub-10-min recordings retain seconds ("4m 12s"). Sub-60s retain seconds only ("42s").
- **Card typography** — Title size `text-[15px]` → `text-[18px]`. Body preview `text-[13px]` → `text-[15px]`.
- **Card timestamps** — Local `formatDate()` ("Feb 19 8:40 PM") replaced with `formatRelativeDate()` from shared formatters.
- **Tag chips** — Container is now `justify-center` in the sidebar panel.
- **Refresh button** — Removed from the header to reduce visual noise; list refreshes on navigation and after mutations.
- **Search bar** — Search icon moved to right side; swaps to × (clear) when query is active.

### Fixed

- **Tag delete race condition** — `pointerdown` fired before `onclick`, causing the global overlay handler to null `tagMenuId` before the delete handler ran. Fixed by replacing the entire inline-confirm approach with a context menu that stops pointer propagation.
- **`openTagAssign` type incompatibility** — Made `event` parameter optional (`event?: MouseEvent`) so the function is assignable to `StyledButton.onclick: () => void`.
- **`$state(null)` type inference in EditView** — Changed to `$state<Transcript | null>(null)` to prevent TypeScript inferring `never` for the transcript variable.

---

## v5.1.0 — TranscribeView Phase 3 UI Redesign

**Date:** 2026-03-07
**Status:** Feature Release

### Overview

Complete visual redesign of all three active states in the TranscribeView — idle, recording, and transcript viewing. Replaces placeholder UI with data-driven informatics, constrained spectrum animation, and a unified button system.

### Added

- **Activity Heatmap** (`ActivityHeatmap.svelte`) — Calendar-year GitHub-style contribution heatmap in the idle state. Month-sectioned columns (Jan → current month mandatory, additional months fitted to available width). Quartile intensity shading. Fully responsive via ResizeObserver.
- **Inline session stats in idle header** — Today's word count, average WPM, and session count as a compact inline strip beneath the greeting when data exists.
- **Live recording timer** — Elapsed `MM:SS` counter in the recording action bar alongside the "Recording in progress…" pulse indicator.
- **Transcript title display** — `transcriptTitle` state populated from `display_name` on `openTranscript()`. Live updates via `transcript_updated` WebSocket event (re-fetches on ID match).
- **`returnToDashboard()` function** — Resets all transcript state and returns to idle; exposed as a "Dashboard" ghost button in the action bar.
- **`StyledButton` `size` prop** — New `size?: "sm" | "md"` prop decouples sizing from color variant. `sm` = `h-8 px-3 text-xs gap-1.5` for action bars. `md` (default) preserves all existing consumers unchanged.

### Changed

- **Idle state layout** — Greeting enlarged to `text-3xl` accent blue; session stats moved inline to header; mic button scaled to 160 × 160 px; old stats grid panel removed.
- **Recording state** — Spectrum visualizer fills the entire workspace panel; action bar carries live timer, pulse indicator, Cancel (left), and Stop & Transcribe (right).
- **Transcript header** — Centered layout: accent-blue `text-xl` title above monospace timestamp. Falls back to timestamp-only when title not yet generated by SLM.
- **Metrics strip** — Stacked label-above-value columns replaced with centered single-line inline format. "Speech Ratio" renamed to "Active Speech". Progress bar widened from `max-w-[160px]` to `max-w-[280px]`.
- **Action bar — Ready/Viewing** — Raw `<button>` Tailwind spaghetti replaced with `<StyledButton size="sm">`. Left cluster: Delete (destructive) → Edit (ghost) → Copy (secondary). Right cluster: Refine (ghost, conditional) → Dashboard (ghost) → New Recording (primary).
- **Action bar — Editing** — Discard (ghost, left) → spacer → Save (primary, right).
- **Transcribing state header** — Removed duplicate `Loader2 + "Transcribing…"` from header; spinner already present in panel center.

---

## v5.0.1 — Post-Migration Bug Fix Pass

**Date:** 2026-03-06
**Status:** Patch Release

### Overview

Bug fix pass addressing runtime regressions discovered after the v5.0.0 CTranslate2 migration. All SLM inference (title generation, insight generation, text refinement) was silently failing. Manual transcript rename was a dead route. Model registry contained dead HuggingFace repos.

### Fixed

- **SLM inference `TypeError` (#42)** — `generate_batch()` requires `List[List[str]]` (string subword tokens), not `List[List[int]]` (integer token IDs). Both `refine()` and `generate_custom()` in `RefinementEngine` were passing `encoded.ids` instead of `encoded.tokens`. Fixed in `src/refinement/engine.py`.
- **SLM output included full prompt (#43)** — `generate_batch()` defaults to `include_prompt_in_result=True`, causing decoded output to contain the entire ChatML prompt prefix. Title generation was returning `"system"` (the first line of the decoded prompt). Added `include_prompt_in_result=False` to both `generate_batch()` call sites.
- **`rename_transcript` route unregistered (#44)** — The `POST /api/transcripts/{id}/rename` handler was defined in `src/api/transcripts.py` but never imported or added to the Litestar router in `src/api/app.py`. Every manual rename was silently 404-ing. Added to both the import block and the route list.
- **Title edit cancelled by WebSocket refresh (#45)** — `TranscriptDetailPanel.svelte` had a `$effect` that reset `editingTitle = false` whenever the `entry` prop changed reference. A `transcript_updated` WebSocket event (e.g. from title gen completing) triggered `loadEntryDetail`, replacing `selectedEntry` with a new object and cancelling any in-progress rename. Fixed by comparing `entry.id` — edit state now resets only when navigating to a different transcript.
- **Dead SLM model repos (#46)** — All four `Michael-Moo/` HuggingFace repos in the model registry returned 401 (account deleted or private). Replaced with verified public alternatives: `jncraton/Qwen3-1.7B-ct2-int8`, `jncraton/Qwen3-4B-ct2-int8`, `ctranslate2-4you/Qwen3-8B-ct2-AWQ`, `ctranslate2-4you/Qwen3-14B-ct2-AWQ`.
- **Fake ASR fast-tier model ID (#47)** — Registry entry `faster-whisper-large-v3-Q5_0` referenced a GGUF quantization format that does not exist in CTranslate2. Replaced with `Zoont/faster-whisper-large-v3-turbo-int8-ct2`.
- **`GET /api/models` `KeyError: 'filename'` (#48)** — `list_models()` in `src/api/system.py` was checking `info["filename"]`, a field that does not exist on CT2 directory models. Fixed to derive local path from `repo.split("/")[-1]` and check `model_file` inside the directory.
- **`download_model` wrong function (#49)** — `download_model()` was calling `download_model_file()` with `model.filename`. CT2 models are directories; fixed to call `download_model_directory()` with `model.repo`.
- **`ModelInfo` TypeScript interface stale (#50)** — Frontend `ModelInfo` interface had `filename: string` instead of `model_file: string`. Updated in `frontend/src/lib/api.ts`.
- **HTTP client log noise (#51)** — `httpx`, `httpcore`, `huggingface_hub.utils._http`, `huggingface_hub.file_download`, and `huggingface_hub.repocard` were flooding stdout at DEBUG/INFO level during model downloads. Clamped to WARNING in `src/core/log_manager.py`.

---

## v5.0.0 — CTranslate2 Universal Backend Migration

**Date:** 2025-07-12
**Status:** Major Release

### Overview

Complete replacement of both inference backends — `pywhispercpp` (ASR) and `llama-cpp-python` (SLM) — with a unified CTranslate2-based stack. ASR now uses `faster-whisper` (CTranslate2 Whisper backend) and SLM uses `ctranslate2` Generator directly. This eliminates the libggml shared-library ordering hack, removes GGML/GGUF model format dependencies, and unifies the inference runtime.

### Changed

- **ASR backend**: `pywhispercpp` → `faster-whisper` (CTranslate2 Whisper). Models are now CT2-format directories from `deepdml/faster-whisper-large-v3-turbo-ct2` and `Systran/faster-whisper-large-v3`.
- **SLM backend**: `llama-cpp-python` → `ctranslate2.Generator` + `tokenizers`. Models are CT2-format Qwen3 directories with `int8_float16` quantization.
- **Model registry**: `ASRModel` and `SLMModel` dataclasses changed from single-file (`filename`) to directory-based (`repo` + `model_file`). GGML/GGUF formats replaced with CTranslate2 format.
- **Provisioning**: ASR and SLM provisioning uses `snapshot_download()` for directories. VAD (Silero) remains as single ONNX file via `hf_hub_download()`.
- **GPU detection**: `pywhispercpp.model.Model.system_info()` → `ctranslate2.get_cuda_device_count()`.
- **initial_prompt**: Re-enabled for ASR transcription — faster-whisper handles prompt tokenization safely (no more SIGSEGV from pywhispercpp 1.4.1).
- **SLM tokenization**: ChatML template applied manually via `_messages_to_chatml()`. Token-level stop conditions via `tokenizer.token_to_id()`.
- **Dependencies**: `pywhispercpp>=1.4.0` and `llama-cpp-python>=0.3.0` replaced with `ctranslate2>=4.5.0`, `faster-whisper>=1.1.0`, and `tokenizers>=0.20.0`.

### Removed

- **libggml ordering hack**: The synchronous `import llama_cpp` pre-import in `ApplicationCoordinator` startup is no longer needed. CTranslate2 has no shared-library conflicts.

---

## v4.4.3 — Backend Quality Hardening

**Date:** 2026-02-28
**Status:** Maintenance Release

### Overview

Comprehensive backend audit pass addressing 14 issues spanning async correctness, database integrity, search performance, API robustness, and test isolation. No user-visible behaviour changes; all improvements are in reliability, correctness, and observability.

### Fixed

- **Blocking SQLite on async event loop (#28)** — Route handlers returning plain `dict` or `list[dict]` now run in a thread pool via `sync_to_thread=True`. Handlers that return a Litestar `Response` stay `async def` and use `asyncio.to_thread()` for individual slow DB calls, keeping the event loop free throughout.
- **`update_config` silent failure (#32)** — The `PUT /api/config` handler now raises `InternalServerException` instead of returning HTTP 200 when the `UpdateConfigIntent` dispatch fails. Previously a failed config write was invisible to the caller.
- **Refinement level not validated (#33)** — `POST /api/transcripts/{id}/refine` now validates that `level` is an integer in `[1, 5]` and returns HTTP 400 with a descriptive message before constructing the intent.
- **LIKE wildcard injection (#31)** — `db.search()` now escapes `%`, `_`, and `\` before building the LIKE pattern. *(Superseded by the FTS5 migration below; escape logic removed from that path.)*
- **Shared DB reads unguarded (#41)** — All read methods (`get_transcript`, `recent`, `search`, `get_projects`, `get_project`, `get_untitled_transcripts`, `transcript_count`) now acquire `_write_lock` before executing, preventing a concurrent multi-step write from being observed in a partial state.

### Changed

- **Full-text search migrated to FTS5 (#30)** — `db.search()` now queries a SQLite FTS5 content-table index (`transcripts_fts`) instead of a full-table LIKE scan. Search is O(log n) rather than O(n), case-insensitive, and uses per-token prefix matching (`"word"*` syntax). An empty query falls back to `recent()`. Three triggers (`transcripts_ai/ad/au`) keep the index in sync automatically; existing rows are backfilled on the v2 migration run.
- **Schema migration system added (#29)** — New `src/database/migrations.py` implements a lightweight forward-only migration runner using a `schema_version` table. No Alembic dependency; future schema changes append to the `MIGRATIONS` list. v1 is the baseline no-op; v2 adds the FTS5 index.
- **GPU status cache converted to `lru_cache` (#34)** — `_detect_gpu_status()` in `system.py` is now decorated with `@functools.lru_cache(maxsize=1)`, replacing a manual module-level `_gpu_status_cache` dict. Tests can call `.cache_clear()` for isolation.
- **GPU status pre-warmed at startup (#37)** — `create_app()` now calls `prewarm_health_cache()`, which fires `_detect_gpu_status()` in a background daemon thread. The first `GET /api/health` returns immediately instead of blocking up to 5 s while `nvidia-smi` runs.
- **Audio recording buffer bounded (#36)** — `RecordingSettings` gains `max_recording_minutes: float = 30.0`. The `AudioService` recording loop breaks when the accumulated sample count reaches this limit and logs a warning, preventing unbounded memory growth for runaway recordings.
- **Global exception middleware added (#39)** — `Litestar` is now constructed with `exception_handlers` for both `HTTPException` (consistent `{"error": "..."}` JSON body) and bare `Exception` (logged 500 with no stack-trace leak).
- **OpenAPI spec enabled (#40)** — `Litestar` is now constructed with `OpenAPIConfig(title="Vociferous API", version=APP_VERSION)`. The `/schema`, `/schema/swagger`, and `/schema/elements` endpoints are live.
- **`TitleGenerator` batch DB reference cached (#38)** — `_batch_retitle_task` now fetches the DB reference once at the top of the method rather than calling `self._db_provider()` on every loop iteration for title writes.

### Quality

- **Coordinator global safety-net fixture (#35)** — `tests/conftest.py` gains an `autouse=True` fixture (`_reset_coordinator_global`) that calls `set_coordinator(None)` after every test unconditionally, guaranteeing no leaked coordinator state even if a test fails before its own teardown.
- All 394 tests pass.

---

## v4.4.2 — Security Hardening & Frontend Bug Fixes

**Date:** 2026-02-24
**Status:** Maintenance Release

### Security

- **Export filename sanitized** — `Path(...).name` is now applied to the `filename` parameter in the `/api/export` route before it reaches the native save dialog. This prevents path traversal sequences in the suggested filename from misdirecting the GTK file chooser to an unintended directory.

### Fixed

- **Section collapse state corrected** — Replaced the `Set`-based collapse tracker in TranscriptsView with a `Map<string, boolean>` that stores explicit user overrides. Sections now have correct defaults (prior-day date groups collapsed, today and project groups expanded) and user toggles are preserved independently of those defaults.
- **Refine state not cleared on transcript switch** — `isRefining` flag and the refine timer are now reset when loading a new transcript in RefineView, preventing a stale spinner from persisting after navigation.
- **Text fallback for sparse transcripts** — RefineView and UserView now use a fallback chain (`text → normalized_text → raw_text`) when accessing transcript content, preventing crashes on transcripts with a null primary text field.
- **Ctrl+A select-all skips input fields** — The global Ctrl+A handler in TranscriptsView and SearchView now returns early when focus is inside an `INPUT` or `TEXTAREA`, restoring native browser select-all behaviour in those contexts.
- **Rename transcript double-submit guard** — `commitTitle` in TranscriptsView is now guarded by an in-flight flag, preventing a duplicate API call if the handler fires twice in quick succession.
- **Transcript title updates immediately after rename** — Local entry state and the entries list are updated optimistically after a successful rename so the new title appears without waiting for a WebSocket event.
- **Debounce timer cleared on SearchView destroy** — The pending debounce timer is now cancelled in the `onMount` cleanup function, preventing a stale search dispatch after the component unmounts.
- **Duplicate event listener removal removed** — The `onDestroy` block in TranscriptsView that duplicated the `onMount` cleanup was removed; listeners are cleaned up once in the existing `onMount` return function.

---

## v4.4.1 — Expansion Fix & Insight Refinement

**Date:** 2026-02-21
**Status:** Maintenance Release

### Fixed

- **Date Header Expansion Corrected** — Older transcript buckets (Yesterday, etc.) now actually expand after a click. Decoupled the initialization logic from the render cycle to prevent UI staleness.
- **Insight Generation Logic Fixed** — Updated `InsightManager` to use the correct SLM inference method, preventing the system prompt from being confused as a transcript for refinement.

### Improved

- **Insight Regeneration Frequency** — The AI-generated dashboard insights and MOTD lines now regenerate more frequently based on the number of captured transcripts (5 for insights, 3 for MOTD), reducing reliance on the 24-hour TTL alone.

---

## v4.4.0 — Project Management Overhaul & UI Consistency Pass

**Date:** 2026-02-18
**Status:** Feature Release

### Overview

Complete overhaul of the Transcriptions view's project management system. Eliminates all legacy "History View" / "Projects View" naming, renames the rename workflow to edit, adds a full conditional delete modal with transcript/subproject fate options, fixes the color picker (removes muting/lightness override system), replaces native selects with dark-themed custom dropdowns, and fixes project header layout, icon ordering, count badge contrast, and inter-group dividers. Followed by a full UI polish pass covering multi-select visual correctness, stats staleness, search layout, and destructive action clarity.

### Changed

- **Transcriptions View naming finalized** — All references to "History View" and "Projects View" purged across the entire codebase. `loadHistory` → `loadTranscripts`, all related state/handler names updated.
- **"Rename Project" → "Edit Project"** — Modal mode `"rename"` renamed to `"edit"` throughout. `RenameResult` → `EditResult`. Tooltip updated.
- **Project header layout corrected** — DOM order is now `[chevron] [name] [edit-btn] [delete-btn] [count]`. Count badge is always rightmost and uses `var(--text-primary)` for legibility.
- **Color picker muting removed** — Entire HSL lightness override system (`hexToHsl`, `hslToHex`, `lightness`, `colorHsl`, `colorSafe`) deleted. Picked hex is used as-is.
- **Swatch grid balanced** — Expanded to 36 swatches (6×6 perfect grid), all vibrant and dark-UI readable.
- **Parent dropdown dark-themed** — Native `<select>` replaced with `CustomSelect` component in both Create and Edit modes.
- **Edit modal shows parent selector** — Parent field now visible when editing a project (hidden only if the project has subprojects, to enforce hierarchy depth limit).
- **`parent_id` passed through edit** — `EditResult` carries `parentId`; `updateProject` call now sends it.
- **Project group dividers** — Increased prominence (`opacity-60`, `my-3`) between top-level project groups.
- **`project_updated` WebSocket handler** — Frontend now reacts to live project update events.

### Delete modal overhaul

- Conditional checkbox layout based on project structure:
  - Always: "Delete transcripts assigned to this project" (unchecked = unassign)
  - Top-level with subprojects: "Promote subprojects to top-level" (unchecked = also delete them)
  - When deleting subprojects: "Also delete transcripts in subprojects"
- Button order: **Delete (left) | Cancel (right)** with `justify-between`.
- Full-stack implementation: `DeleteProjectIntent` carries three new boolean flags; `delete_project()` in DB implements conditional logic for all combinations within a single write-lock transaction.

### UI Polish Pass

- **Multi-select accent bar** — Selection highlight bar (`w-0.5` blue left edge) now renders on all transcript rows, including project-assigned ones. Previously only appeared in the Unassigned section due to an `{:else}` branch error.
- **TranscribeView stats corrected** — `loadRecentSessions()` was called with a hard limit of 20 transcripts, producing a wrong session count. Limit raised to 500. Stats now also reload on every navigation to the Transcribe view, not only on `transcription_complete`.
- **UNASSIGNED count badge removed** — The total count on the Unassigned section header was redundant noise — it always equaled the sum of the child date-group badges beneath it. Removed. Date-group counts remain.
- **Project row spacing** — Project header rows gain `4px` left and `8px` right margin so they don't butt against the scrollbar. Unassigned header matches.
- **Date-stamp count badge** — Promoted from `text-[10px] text-[var(--text-tertiary)]` (near-invisible) to `text-xs font-semibold text-[var(--text-primary)]`.
- **Search input border** — Fixed. All other inputs in the app use `border-[var(--shell-border)]`; the SearchView input was incorrectly using `border-[var(--text-tertiary)]`.
- **Search placeholder** — Changed from "Filter…" (wrong mental model) to "Search transcripts…".
- **RefineView "Discard" → "Delete Result"** — "Discard" had the same visual weight as "Re-run" but calls `deleteVariant()` — permanent storage deletion. Renamed to "Delete Result", given Trash2 icon, danger red hover styling, and a tooltip: "Permanently removes this refinement from storage."
- **Settings maintenance grid** — Card layout promoted to `lg:grid-cols-3` so all three maintenance cards (Transcriptions, Titles, Engine) display in a balanced three-column row at large viewports.

### Fixed

- **`ProjectModal` Svelte 5 warnings** — Prop-initialized `$state` now uses `$effect` for reactive initialization from `mode`/`target` props. `heading` converted to `$derived`. `tabindex="-1"` added to dialog element. `onchange` callback typed explicitly.
- **Frontend typecheck** — `npm run check` passes with 0 errors and 0 warnings.

---

## v4.3.0 — Unified Transcriptions View, Batch Retitling & Auto-Title on Refine

**Date:** 2026-02-18
**Status:** Feature Release

### Overview

Consolidates the History and Projects views into a single **Transcriptions** view with inline project management. Adds batch retitling for existing untitled transcripts and automatic re-titling after SLM refinement.

### Added

- **Batch Retitling** — New "Retitle All Untitled" button in Settings → Maintenance. Scans all transcripts missing a display name, generates SLM-powered titles sequentially with skip logic for too-short or too-long text, and reports progress via WebSocket in real time (progress bar + processed/skipped counters).
- **Auto-Retitle on Refine** — When enabled (default: on), automatically generates a new title after SLM refinement completes. Controlled by `auto_retitle_on_refine` toggle in Settings → Output & Processing.
- **Inline Project Management** — Create, rename, and delete projects directly from the Transcriptions view, with a full color picker (wheel/gradient + swatches), optional parent selection, and confirmation-guarded deletion.
- **`get_untitled_transcripts()`** database method for querying transcripts with NULL or empty display names.
- **`BatchRetitleIntent`** for dispatching batch retitle operations through the CommandBus.
- **`batch_retitle_progress`** WebSocket event type for real-time progress reporting.

### Changed

- **History + Projects → Transcriptions** — The sidebar now shows a single "Transcriptions" entry with a `Library` icon. The old "Projects" view and its separate route are removed. Project filtering, creation, and deletion are all inline in the unified view.
- **Removed `ProjectsView.svelte`** — Orphaned component deleted; all project management lives in the unified Transcriptions view.
- **Removed `"projects"` from `ViewId`** — Navigation type union no longer includes the dead route. The normalization hack (`projects → history`) is gone.

### Quality

- Navigation store simplified: no more view-ID aliasing or dead branches.

### Fixed

- **ASR Segfault on Stop/Transcribe** — Disabled `initial_prompt` passthrough for `pywhispercpp==1.4.1` in runtime transcription calls due to a binding-level pointer lifetime bug that can trigger SIGSEGV. Startup ordering still preloads `llama_cpp` before ASR model load to avoid ggml/CUDA symbol-order crashes.

---

## v4.1.4 — Database Safety & Event Bridge Fix

**Date:** 2026-02-18
**Status:** Bugfix / Stability Release

### Overview

Critical stability fixes for database concurrency and event propagation issues identified during post-refactor validation.

### Fixed

- **Event Bridge Whitelist**: Added missing `insight_ready` and `motd_ready` events to the WebSocket bridge whitelist. Frontend integrations relying on these events (like dashboard updates) now work correctly.
- **Database Thread Safety**: Added a recursive `threading.Lock` around all write operations in `TranscriptDB`. This prevents potential race conditions when multiple threads (Apply Edit vs Refinement vs Ingestion) attempt to write to the shared SQLite connection simultaneously.
- **InsightCache IO Thrashing**: `InsightCache` now loads data into memory once at initialization. Property access no longer triggers a disk read on every call.
- **Database Cascade Logic**: Simplified `clear_all_transcripts` to rely on SQLite `ON DELETE CASCADE` for cleaning up variants, removing unnecessary manual deletion code.

---

## v4.1.3 — API Correctness & Stats Extraction

**Date:** 2026-02-18
**Status:** Bugfix / Refactor Release

### Overview

Three targeted fixes identified during post-refactor review.

### Changed

- **Extracted `src/core/usage_stats.py`** — the 65-line `_compute_stats` closure
  buried inside `ApplicationCoordinator._init_insight_manager()` is now a
  proper module-level function `compute_usage_stats(db)`. Both `InsightManager`
  and `MOTDManager` call the same function directly. The `# noqa: SLF001`
  private-access workaround in `_init_motd_manager` is gone. The logic is
  now independently testable. Incidentally also fixes a double word-iteration
  bug in the original (single-word fillers and vocab collection were two
  separate passes over the same list).
- **`/api/engine/restart` now dispatches via CommandBus** — the route was
  calling `coordinator.restart_engine()` directly, bypassing the intent
  architecture entirely despite a `RestartEngineIntent` existing.
- **Fixed stale `_is_recording` access in `/api/health`** — after the
  coordinator decomposition, `_is_recording` moved to `RecordingSession`.
  The old `getattr(coordinator, "_is_recording", False)` was silently
  returning `False` always. Now reads `coordinator.recording_session.is_recording`.
- **GPU detection result is cached** — `_detect_gpu_status()` previously
  spawned an `nvidia-smi` subprocess on every `/api/health` poll. Result
  is now cached after the first call.

### Quality

- All 387 tests pass.

---

## v4.1.2 — Coordinator Decomposition (God Object Slain)

**Date:** 2026-02-18
**Status:** Refactor Release

### Overview

Structural refactor of `ApplicationCoordinator` to eliminate its God Object status.
All intent handler logic has been extracted into focused, independently testable
domain handler classes. The coordinator is now a true composition root.

### Changed

- **`ApplicationCoordinator` reduced from 1181 → 774 lines.** All 15 `_handle_*`
  methods, the recording pipeline (`_recording_loop`, `_transcribe_and_store`),
  and the clipboard helper have been extracted.
- **New `src/core/handlers/` package** with five handler classes:
  - `RecordingSession` — recording state machine, ASR model lifecycle,
    audio→transcribe→store pipeline, system clipboard copy.
  - `TranscriptHandlers` — delete, clear, and commit-edits intents.
  - `ProjectHandlers` — create, update, delete, and assign-project intents.
  - `RefinementHandlers` — SLM refinement pipeline.
  - `SystemHandlers` — config update and engine restart intents.
- **`_register_handlers()`** now instantiates handler objects and wires them into
  the `CommandBus` — it no longer references `self._handle_*` methods.
- **ASR model lifecycle** moved into `RecordingSession.load_asr_model()` /
  `unload_asr_model()`, keeping the model co-located with the code that uses it.

### Quality

- All 387 tests pass.
- Each handler class is independently constructable and testable without
  instantiating the full coordinator or any hardware services.

---

## v4.1.1 — Edit Flow & Input Reliability Fixes

**Date:** 2026-02-18
**Status:** Bugfix Release

### Overview

Patch release focused on edit-session safety, transcription edge-case handling, and launcher/input reliability.

### Fixed

- **Hard edit-session navigation lock:** While actively editing, sidebar navigation is blocked until Save or Discard completes, preventing accidental context loss and half-finished edits.
- **Cross-view edit routing consistency:** Edit actions in Search, Projects, Refine, and History now open the centralized Transcribe editor directly in edit mode and return users to the originating view after completion.
- **Transcribe "New" action behavior:** Starting a new transcript now immediately begins recording instead of waiting for extra interaction.
- **Refine/Projects action wiring:** Refine and Edit actions now route to the intended destinations consistently across views.
- **Silent-audio hallucination guard:** Added explicit effective-silence detection before ASR inference to prevent non-empty hallucinated output from empty/silent recordings.
- **Hotkey stop robustness:** Improved chord/reset handling so stop/toggle hotkeys remain reliable after keyboard layout or input-device changes.
- **Linux taskbar identity:** Updated desktop integration metadata and window identity hints so launcher/taskbar icon matching is consistent.

### Quality

- Frontend production build passes.
- Regression tests for transcription silence detection pass.

---

## v4.1.0 — Multi-Select & UI Polish

**Date:** 2026-02-16
**Status:** Feature Release

### Overview

File-explorer-style multi-selection across all transcript views, batch project assignment, batch deletion, and comprehensive UI/UX polish. Full linter, type-checker, and test suite cleanup.

### Added — Multi-Selection System

- **`SelectionManager`** (`frontend/src/lib/selection.svelte.ts`): Reusable Svelte 5 rune-based selection manager with Click (select one), Ctrl+Click (toggle), Shift+Click (range select), Ctrl+Shift+Click (add range), Ctrl+A (select all), Escape (clear).
- **TranscriptsView multi-select**: Selection count header, multi-select detail panel with bulk Assign/Delete buttons, keyboard hints, right-click auto-select for context menus.
- **SearchView multi-select**: Same selection UX plus newly added project assignment system (was previously missing from SearchView entirely). Conditional single/multi action bar.
- **TranscriptsView multi-select (project trees)**: Selection across expanded project transcript trees. Range selection walks the full display-order tree (root projects → children → expanded transcripts).
- **Batch API functions** (`batchAssignProject`, `batchDeleteTranscripts`): Sequential loop over individual intent dispatches — no backend changes required.

### Changed — UI Polish

- **SettingsView**: Removed `small` prop from 3 CustomSelect dropdowns (Spectrum Type, UI Scale, Context Size); bumped number input max-width from 200px to 280px.
- **UserView**: Removed `max-w-[960px]` cap — dashboard now fills available width.
- **All transcript context menus**: Header dynamically shows batch count ("Assign N transcripts to project") when multi-selected.

### Fixed — Code Quality

- **Ruff**: Fixed 3 unused variable warnings in test files (prefixed with `_`).
- **MyPy**: Fixed all 28 type errors (was 0 errors, now 0 errors):
  - `ApplicationCoordinator`: Added proper `TYPE_CHECKING` imports and `Optional` type annotations for 7 lazily-initialized service attributes (killed 15 errors in one shot).
  - `system.py`: Fixed `ASRModel | SLMModel` union type for model lookup.
  - `db.py`: Replaced `Ellipsis` sentinel with proper `_Unset` enum for `update_project()` parent_id parameter.
  - `engine.py`: Added `type: ignore` for llama-cpp-python's unusable chat completion stubs.
  - `provisioning/core.py`: Removed deprecated `local_dir_use_symlinks` kwarg from `hf_hub_download()`.
  - `log_manager.py`: Added `dict[str, object]` annotation for `extra`.
  - `slm_runtime.py`: Added `dict[int | str, dict[str, Any]]` annotation for `levels`.
  - `on_closing()`: Fixed `-> True` return annotation to `-> bool`.
  - Tests: Removed 3 stale `type: ignore[misc]` comments, fixed generator fixture return type.
- **Pytest**: 374 tests, 0 failures. Fixed 3 provisioning test assertions that expected the removed `local_dir_use_symlinks` kwarg.

---

## v4.0.0 — Architecture Rebuild

**Date:** 2026-02-14
**Status:** Major Release

### Overview

Complete architectural rebuild from PyQt6 desktop application to a modern web-native stack. The core transcription pipeline and data model are preserved; the UI, configuration, API, and runtime layers are replaced.

### Changed — Stack

- **UI Shell:** PyQt6 → **pywebview** (GTK on Linux, Cocoa on macOS, EdgeChromium on Windows)
- **Frontend:** Custom Qt widgets → **Svelte 5** SPA with **Tailwind CSS v4**, built via **Vite 6**
- **API Layer:** Direct Python calls → **Litestar** REST + WebSocket server on `localhost:18900`
- **ASR Engine:** faster-whisper (CTranslate2) → **pywhispercpp** (whisper.cpp, GGML models)
- **SLM Engine:** transformers pipeline → **llama-cpp-python** (llama.cpp, GGUF models)
- **Configuration:** Hand-rolled YAML + ConfigManager → **Pydantic Settings** (typed, validated, JSON persistence with atomic writes)
- **Database:** SQLAlchemy ORM → **raw sqlite3** with dataclass models (3 tables: transcripts, transcript_variants, projects)

### Changed — Architecture

- **Event System:** Qt signals → **EventBus** (thread-safe pub/sub with `threading.Lock`)
- **Command System:** Direct method calls → **CommandBus** (intent-based dispatch, preserved from v3)
- **WebSocket:** Real-time event bridge from EventBus to frontend via **Litestar WebSocket Listener** with `connection_lifespan`
- **Thread-safe broadcast:** `ConnectionManager` stores event loop reference, uses `call_soon_threadsafe` for sync→async bridging

### Added

- **Mini Widget:** Compact floating recording indicator (MiniWidget.svelte) — frameless, transparent, always-on-top pywebview window with pulsing dot and elapsed timer
- **Onboarding Flow:** Startup ASR model verification with `onboarding_required` event
- **Multi-page Vite Build:** Separate entry points for main app and mini widget
- **Unit Test Suite:** 56 tests covering settings, command bus, event bus, database, and model registry

### Preserved

- **Process-based IPC:** `core_runtime/` subprocess with CRC32-framed stdin/stdout PacketTransport (unchanged)
- **Transcript Immutability:** Raw captures remain immutable; edits stored as variants
- **Model Registry:** Centralized ASR/SLM model catalog
- **Provisioning System:** HuggingFace Hub model downloads with integrity checks

### Removed

- PyQt6 and all 73+ Qt widget/view files
- SQLAlchemy, faster-whisper, CTranslate2, transformers, torch dependencies
- YAML configuration system (ConfigManager, config_schema.yaml)
- Legacy state manager, signal bridge, and unused database DTOs

---

## v3.x Legacy Changelog

> The following entries document the v3.x release series, which used PyQt6, faster-whisper, and SQLAlchemy.

---

## v3.0.18 - Feature: Database Backup Export

**Date:** 2026-02-06
**Status:** Feature

### Context

**VACUUM INTO** = SQLite operation that creates a consistent backup of the database file, ensuring no data is lost if the app crashes.

### Added

- **Database backup:** New "Backup Database…" button in Settings → History Management exports a consistent copy of the SQLite database via `VACUUM INTO`, with a WAL-checkpoint file-copy fallback.
- `HistoryManager.backup_database(dest)` encapsulates the logic; `MainWindow` wires a standard save-file dialog.

---

## v3.0.17 - Feature: Frameless Window Edge Resize

**Date:** 2026-02-06
**Status:** Bugfix / UX

### Fixed

- **Edge resize:** `MainWindow` now supports resizing from all four edges and corners using `startSystemResize()` with an 8 px grip zone, matching the behavior users expect from a frameless window.
- Mouse cursor updates to the correct resize arrow on hover and resets on leave.

---

## v3.0.16 - Bugfix: Project Color Refresh on Data Change

**Date:** 2026-02-06
**Status:** Bugfix

### Fixed

- **TranscriptsView project colors:** `TranscriptsView._handle_data_changed` now handles `entity_type == "project"` events by calling `TranscriptionModel.refresh_project_colors()`, so color-identifier badges update without a manual refresh.

---

## v3.0.15 - Bugfix: Export Dialog Browse Button Height

**Date:** 2026-02-06
**Status:** Bugfix / UI

### Fixed

- **Browse button sizing:** Removed `setFixedHeight(42)` on the Browse button in `ExportDialog`, which conflicted with the stylesheet's `min-height: 44px`, causing a 2 px visual glitch. Vertical alignment centred via layout flag instead.

---

## v3.0.14 - Improvement: Versioned Database Migrations

**Date:** 2026-02-06
**Status:** Improvement / Safety

### Changed

- **Migration framework:** Replaced ad-hoc `ALTER TABLE` try/except migrations with a `schema_version` table and a numbered migration registry. Each migration runs inside an explicit transaction (`engine.begin()`), and the version counter advances atomically.
- Existing databases auto-bootstrap to the correct version on first run.

---

## v3.0.13 - Improvement: Engine Subprocess Logging

**Date:** 2026-02-06
**Status:** Improvement

### Changed

- **Engine log file:** The `core_runtime` subprocess now writes to `vociferous_engine.log` via a `RotatingFileHandler` (5 MB, 2 backups) in the same log directory as the main application, in addition to its existing stderr handler.
- Falls back to stderr-only if file handler setup fails.

---

## v3.0.12 - Bugfix: Refinement Acceptance Stores Variant

**Date:** 2026-02-06
**Status:** Bugfix

### Context

**Refinement** = AI-powered text enhancement using a Small Language Model (SLM).  
**Variant** = An immutable copy of a transcript at a point in time (original, refined, edited, etc.).

### Fixed

- **Variant persistence:** Accepting a refined transcription now stores an immutable variant (`kind="refined"`) via `HistoryManager.add_variant_atomic` before updating the normalised text, preserving the full refinement history per the data model's design intent.

---

## v3.0.11 - Refactor: Replace `SLMService` with `SLMRuntime` (P1)

**Date:** 2026-01-29
**Status:** Refactor / P1

### Changed

- **Runtime consolidation:** Replaced the legacy monolithic `SLMService` with a focused `SLMRuntime` (`src/services/slm_runtime.py`) that is responsible solely for loading provisioned models, running inference, and managing enable/disable lifecycle. The `ApplicationCoordinator` now wires and interacts with `SLMRuntime` directly.
- **UI model registry:** UI surfaces that previously used `SLMService.get_supported_models()` now read models from the canonical registry `src/core/model_registry.MODELS`.
- **MOTD compatibility:** Added a small `motd_ready` signal and `generate_motd()` shim in `SLMRuntime` to preserve existing MOTD plumbing during migration.
- **Tests & docs:** Updated and removed tests that depended on legacy behaviors; refreshed architecture docs (`docs/wiki/Architecture.md`, `docs/wiki/Refinement-System.md`) to reflect the change.

### Removed

- **Legacy service:** Deleted `src/services/slm_service.py` and removed in-band provisioning/GPU-confirmation and request-queueing responsibilities from the runtime. Provisioning should be performed by provisioning tooling (`scripts/provision_models.py`) or separate services.

### Impact & Rationale

- **Why:** Converging on a single, focused runtime reduces maintenance burden, eliminates duplicated behavior, and makes lifecycle semantics easier to reason about.
- **Effort:** Medium (refactor + tests + docs). All tests pass locally after the migration.

---

## v3.0.10 - Safety: SLM request queue dedupe & max size (P2)

**Date:** 2026-01-29
**Status:** Improvement / Safety

### Context

**Deduplication** = prevent duplicate refinement requests from flooding the queue if user clicks multiple times.

### Changed

- **SLM queue safety:** Added deduplication of queued refinement requests by `transcript_id` and a configurable queue size `refinement.max_queue_size` (default: `5`). Duplicate requests now replace pending entries (emits "Request updated in queue.") and requests that exceed the queue limit are rejected with a user-facing status message and `refinementError`.

---

## v3.0.9 - Improvement: Atomic model installs & manifest-based validation (P1)

**Date:** 2026-01-29
**Status:** Bugfix / P1

### Context

**Atomic** = all-or-nothing operation: model installation either completes fully or fails completely, preventing partial/broken installs.

### Fixed

- **Atomic provisioning:** `provision_model()` now converts artifacts into a temporary install directory and atomically moves the directory into place on success to prevent partial installs from being treated as valid.
- **Artifact manifest & checksums:** A `manifest.json` is written for each installed model containing SHA256 checksums for key artifacts; `validate_model_artifacts()` uses the manifest to verify file integrity and detect corruption or mismatches.
- **Cleanup on failure:** Partial conversion directories and temp downloads are cleaned up on failure (no half-installed models remain in the cache).
- **Tests:** Added unit tests that assert manifest creation, checksum verification, and proper cleanup when conversion fails.

---

## v3.0.8 - Bugfix: Atomic config saves (P1)

**Date:** 2026-01-29
**Status:** Bugfix / P1

### Context

**Atomic write** = use a temporary file + `os.replace()` to guarantee config is either fully saved or unchanged. Prevents corruption if the app crashes mid-save.

### Fixed

- **Crash-safe config persistence:** `ConfigManager.save_config` now performs atomic writes using a temporary file, fsync, and `os.replace()` to avoid partial/corrupt `config.yaml` files on crashes or power loss. The method also writes an optional `.bak` backup of the previous config when present.
- **Robustness:** The implementation cleans up temporary files on failure and raises on unrecoverable write errors so callers can react appropriately.
- **Tests:** Added tests to assert temp-file cleanup on failure and `.bak` creation on success.

---

## v3.0.7 - Bugfix: SLM GPU confirmation non-blocking fix

**Date:** 2026-01-29
**Status:** Bugfix / P0

### Context

**SLM** (Small Language Model) provisioning required GPU confirmation from users. Previous implementation used blocking waits that froze the UI.

### Fixed

- **SLM GPU confirmation deadlock:** Removed legacy blocking primitives (`QWaitCondition`/`QMutex`) from `SLMService` and replaced the blocking wait flow with an asynchronous signal/queued-invoke pattern. The service now emits `askGPUConfirmation` and returns immediately; the UI confirmation handler invokes `submit_gpu_choice` using a queued call so the choice is processed on the service thread.
- **Timeout fallback:** Added/ensured a 30s GPU confirmation timeout that defaults to CPU when no response is received.
- **Thread-safety & test-hardened coordinator:** The `ApplicationCoordinator` now safely invokes `initialize_service`, `generate_motd`, and `submit_gpu_choice` using a queued invocation when possible and falls back to direct calls when the service is mocked in tests.
- **Tests:** Added unit tests verifying that initialization runs on the SLM service thread and that the GPU confirmation flow resumes initialization via queued invocation.

---

## v3.0.6 - Maintenance: Test Suite Recovery and Venv Integrity

**Date:** 2026-01-30
**Status:** Maintenance / Bugfix

### Context

Tests were failing due to broken import paths in the virtual environment. This fix ensures the test suite runs correctly using `scripts/run_tests.sh`.

### Added

- **Test Runner**: Added `scripts/run_tests.sh` to provide an authoritative way to execute the test suite within the project's virtual environment.
- **Environment Discovery**: Added `pythonpath = ["src"]` to `pyproject.toml` to ensure consistent module discovery across all platforms.

### Fixed

- **Test Collection**: Resolved 14+ `ModuleNotFoundError` errors caused by legacy imports of the defunct `src.provisioning.core` module.
- **Path Resolution**: Fixed pathing errors in test utilities that prevented script detection when run from the repository root.
- **Legacy Tests**: Purged or updated tests targeting removed private methods (`_validate_artifacts`, `_run_conversion`) in `SLMService`.

### Changed

- **Testing Philosophy**: Updated `docs/wiki/Testing-Philosophy.md` to document the new `scripts/run_tests.sh` workflow.

---

## v3.0.5 - Refactor: SLM Service Decomposition

**Date:** 2026-01-29
**Status:** Refactor

### Context

**SLM** = Small Language Model service for text refinement. This refactor broke a large service into focused modules.

### Changed

- **SLM Service Refactor**: Decomposed `src/services/slm_service.py` into focused modules:
  - `src/services/slm_types.py`: Centralized `SLMState` and shared signals.

  - `src/services/slm_background_workers.py`: Isolated `ProvisioningWorker` and `MOTDWorker`.

  - `src/services/slm_utils.py`: Extracted GPU discovery and artifact validation.

- **Deduplication**: Unified `SLMState` and `SupportedModel` definitions between `SLMService` and `SLMRuntime`.

---

## v3.0.4 - Feature: Provisioning Isolation

**Date:** 2026-01-29
**Status:** Feature / Refactor

### Context

**Provisioning** = downloading and setting up speech-to-text models (Whisper and SLM). This separates provisioning into a standalone library for easier maintenance.

### Added

- **Provisioning Library**: New `src.provisioning` package for centralized model management.
- **CLI Tool**: `vociferous-provision` (via `scripts/provision_models.py`) now wraps the new library with improved diagnostics.
- **Dependency Lock**: Added `requirements.lock` for deterministic environments.
- **Startup Integrity**: Strict environment check in `src/main.py` prevents startup if critical dependencies are missing.

### Changed

- **Runtime Isolation**: Removed inline `pip install` suggestions and subprocess conversion logic from `ProvisioningWorker`. It now delegates to the robust provisioning library.
- **Fail Fast**: The application now hard-fails with a clear error message at startup if the environment is incomplete, rather than crashing during operation.

---

## v3.0.3 - Bugfix: Remove legacy DB detection

**Date:** 2026-01-28
**Status:** Bugfix

### Changed

- **Removed** legacy schema detection and automatic reset:
  - Removed `DatabaseCore._check_legacy_schema` and `DatabaseCore._create_backup` (no automatic backup/migration on legacy `schema_version` DBs). Users with existing legacy DBs must manually backup/migrate before upgrading. See `docs/wiki/History-Storage.md` for guidance.

---

## v3.0.2 - Documentation Styling and Accessibility

**Date:** 2026-01-19
**Status:** Documentation Release

### Changed

- **Wiki content reformatting** — Eliminated all emojis and purely decorative symbols from the entire GitHub Wiki documentation suite (14 pages).
- **GitHub Wiki best practices** — Standardized formatting across all wiki pages, replaced manual warning icons with GitHub-native alert blocks (`[!TIP]`, `[!WARNING]`, etc.), and converted status symbols (`✓`, `❌`) to text-based equivalents (`Yes`, `No`) for improved accessibility and professional presentation.

---

## v3.0.1 - Desktop Entry Launcher Fixes

**Date:** 2026-01-19
**Status:** Major Release — Production Ready

### Added

- **Complete GitHub Wiki:** 14 pages covering installation, architecture, UI views, refinement system, and testing strategy
- **Architecture documentation:** Mermaid diagrams, component responsibilities, threading model, and design patterns
- **Design system:** Color scales, typography, spacing tokens, and unified stylesheet patterns

### Changed

- **Documentation standards:** Repository-first authority with all diagrams traceable to source code
- **Accessibility:** Converted emoji and symbols to text for inclusive design

---

## v3.0.0 - Beta Release: Production-Ready with Complete Documentation

**Date:** 2026-01-19
**Status:** Major Release — Beta

### Summary

Vociferous v3.0.0 marks the transition to a production-ready, fully documented release. This version includes a comprehensive GitHub Wiki (14 pages), complete Mermaid diagram audit with repository-backed architecture visualizations, and validated architecture documentation. All architectural invariants are documented, all views are explained with capabilities matrices and state machines, and the entire system is now suitable for professional deployment and contribution.

### Added

**Complete GitHub Wiki (14 Pages):**

```text
docs/wiki/
├── Home.md                               # Landing page with technology stack
├── Getting-Started.md                    # Installation and first-run guide
├── Architecture.md                       # System design (Mermaid flowchart)
├── Design-System.md                      # Design tokens and styles
├── Data-and-Persistence.md               # Database layer (Mermaid ER)
├── UI-Views-Overview.md                  # View architecture (Mermaid)
├── Refinement-System.md                  # AI refinement (Mermaid)
├── View-Transcribe.md                    # Transcription view (Mermaid)
├── View-History.md                       # History browser (Mermaid)
├── View-Search.md                        # Search interface (Mermaid)
├── View-Refine.md                        # AI refinement UI (Mermaid)
├── View-Settings.md                      # Configuration view
├── View-User.md                          # User metrics view
├── Testing-Philosophy.md                 # Test strategy (2-tier)
├── DIAGRAM_AUDIT_REPORT.md               # Complete diagram audit (planning, execution, validation)
├── MERMAID_VALIDATION_REPORT.md          # Post-conversion validation (22 blocks verified)
├── WIKI_PLAN.md                          # Planning document
└── phase2/                               # 14 trace reports (per-page)
    ├── TRACE_*.md
    └── ...
```

**Architecture Documentation:**

- **Architecture.md** — Layered architecture diagram (Mermaid flowchart), component responsibilities, threading model, ApplicationCoordinator design pattern
- **Design-System.md** — Color scales (Gray/Blue/Green/Red/Purple), typography, spacing (S0-S7), unified stylesheet patterns
- **Data-and-Persistence.md** — Entity-relationship diagram, ORM models (Transcript, Project, TranscriptVariant), dual-text invariant, HistoryManager facade
- **UI-Views-Overview.md** — View architecture, BaseView protocol, Capabilities system, ActionDock, navigation flow
- **View-Transcribe.md** — Live recording view, WorkspaceState machine, capabilities matrix, MOTD integration
- **View-History.md** — Master-detail browser, TranscriptionModel, database reactivity via SignalBridge
- **View-Search.md** — Tabular search interface, SearchProxyModel, preview overlay, multi-select handling
- **View-Refine.md** — AI-powered text refinement, side-by-side comparison, strength selector, custom instructions
- **View-Settings.md** — Configuration mutations, custom widgets (ToggleSwitch, HotkeyWidget, StrengthSelector), validation
- **View-User.md** — Usage metrics, personalization, application info, credits, insights generation
- **Refinement-System.md** — SLM lifecycle, provisioning flow, state machine, model registry, GPU memory management
- **Getting-Started.md** — Installation, first run, Wayland setup, troubleshooting, default configuration
- **Testing-Philosophy.md** — Two-tier test strategy, fixtures, lock prevention, architecture guardrails
- **Home.md** — Landing page with technology stack, navigation, screenshots, links

Every page includes:

- Trace points to repository source files (class names, line numbers)
- State diagrams and sequence flows (Mermaid)
- Capabilities matrices for views
- Examples and configuration details
- Internal wiki cross-links

**Mermaid Diagram Suite:**
Full audit of wiki diagrams with 4 conversions applied:

- **Architecture.md** — ASCII layered architecture → Mermaid `flowchart TB` with 4 subgraphs (UI, Core, Runtime, Database layers)
- **Refinement-System.md** — ASCII component stack → Mermaid `flowchart TB` with proper hierarchy
- **Refinement-System.md** — Enhanced SLMState machine with `WAITING_FOR_USER` transition and error recovery paths
- **View-Transcribe.md** — Aligned WorkspaceState diagram with enum; added `VIEWING` state and `RECORDING → IDLE` cancel transition

All conversions verified with 7 trace points per diagram and validated against GitHub's Mermaid renderer.

**Audit & Validation Reports:**

- **DIAGRAM_AUDIT_REPORT.md** — Complete audit of all 14 wiki pages, classifying 100+ diagrams by type, conversion feasibility, and evidence traces
- **MERMAID_VALIDATION_REPORT.md** — Post-conversion validation confirming syntax validity, semantic accuracy, and repository-backed nodes/edges

### Changed

- **CHANGELOG.md** — Added comprehensive v3.0.0 entry with full documentation of wiki pages, diagram conversions, and validation results
- **docs/wiki/** — 14 production-ready wiki pages with Mermaid diagrams and trace points
- **docs/wiki/DIAGRAM_AUDIT_REPORT.md** — 3-part audit report (planning, execution, validation)
- **docs/wiki/MERMAID_VALIDATION_REPORT.md** — Post-conversion validation with 22 Mermaid blocks verified

### Not Changed (Intentional)

The following were intentionally NOT converted to Mermaid as they represent pixel-geometry UI layouts rather than architectural structures:

- MainWindow layout diagrams (spatial arrangement, not hierarchy)
- All view layout diagrams (Form, master-detail, table, cards layouts)
- These remain as ASCII for clarity of visual intent

### Documentation Architecture

All documentation follows strict repository authority with:

- Zero invented components or behaviors
- All diagrams traceable to source files (file path + class/function name)
- Prose flows explained with "Derived from implementation" citations
- Internal links validated
- ASCII layouts preserved where appropriate (UI mockups, pixel-geometry representations)
- Mermaid conversions used only for structural/behavioral diagrams

### Documentation Standards Established

This release establishes documentation standards for future development:

1. **Repository-First Authority** — Documentation never invents; it traces to code
2. **Trace Points Required** — Every diagram includes source file references
3. **Mermaid for Architecture** — Structural/behavioral flows use Mermaid; pixel layouts remain ASCII
4. **Dual Reports** — Complex documentation includes audit + validation reports
5. **Cross-Link Integrity** — All internal links maintained through automated validation

### Validation & Quality Assurance

- All 22 Mermaid blocks syntactically valid (GitHub-compatible)
- 14 wiki pages internally linked and cross-referenced
- 6 image paths verified (docs/images/)
- Zero unevidenced nodes or edges in any diagram
- README.pdf successfully generated and tested
- All tests pass: `ruff check`, `mypy`, `pytest`

### Commits & Reproducibility

This release is fully reproducible. All wiki content is:

- Derived from repository code via trace points
- Validated against Mermaid rendering rules
- Cross-linked and consistent
- Suitable for git history and attribution

---
