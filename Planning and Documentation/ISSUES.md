Issue #1: [BUG] Whisper/Voxtral engine selection uses Canary model by default
Labels: `type:bug`, `area:cli`, `priority:high`, `status:proposed`

## Summary
**What:** CLI `--engine whisper_turbo|voxtral_local` builds EngineConfig with Canary model when app default engine is Canary. 
**Outcome:** Engine-specific defaults are enforced; cross-engine model names auto-remap or warn, preventing wrong-model load failures.

## Rationale
### Context
`build_transcribe_configs_from_cli` reuses `app_config.model_name` when CLI engine differs; `normalize_model_name` does not reject Canary names for whisper/voxtral.
### Why This Approach
* **Primary value:** Prevents runtime init failures and wrong engine loads.
* **Technical advantage:** Engine-kind-safe defaults; guards cross-engine misuse.
* **User impact:** `--engine whisper_turbo` works without extra flags.
* **Operational impact:** Fewer support/debug incidents over model resolution.
* **Long-term value:** Consistent normalization rules per engine-kind.
### Why Not Alternatives
* Documenting pitfall leaves failures unresolved.
* Forcing users to always pass model hurts UX.
* **Decision summary:** Auto-remap/guard to engine defaults with warning is preferred.

## Strategy: Engine-specific default resolution
**One-line description:** Ensure engine configs choose the target engine’s default/alias and remap cross-engine names.

## Phased Execution Plan
### Phase 1 (Immediate)
**Objective:** Correct config/model resolution when CLI engine differs from app default.
**Affected Areas:**
* `src/cli/helpers.py` — avoid reusing app_config model when engine differs; pick engine default.
* `src/engines/model_registry.py` — remap Canary names when kind is whisper/voxtral.
**Expected Behavior:** Whisper/Voxtral selections always use whisper/voxtral models; Canary remains unchanged.

### Phase 2 (Next Release)
**Objective:** Regression coverage for engine/model resolution.
**Affected Areas:**
* `tests/cli` or `tests/engines` — cases with app engine=canary and CLI engine=whisper/voxtral.
**Expected Output:** Tests assert resolved `model_name` matches engine default/alias.

### Phase 3 (Future)
**Objective:** Optional strict validation with warnings.
**Affected Areas:**
* `model_registry.py` — optionally emit warning on remap; docs note.

## Decisions Required
1. Should cross-engine names auto-remap (proposed) or hard error? (Recommend remap + warn.)
2. Emit logger warning on remap? (Recommend yes.)

## Implementation Checklist
* [ ] Update `build_transcribe_configs_from_cli` to ignore `app_config.model_name` when engine differs; use engine default/alias.
* [ ] Add cross-engine guardrail in `normalize_model_name` to remap Canary names for whisper/voxtral.
* [ ] Add regression tests for engine/model resolution matrix.
* [ ] Document remap/warning behavior if added.

## Testing Strategy
* CLI/config bundle tests asserting resolved model names for whisper/voxtral when app default is Canary.
* Unit tests for `normalize_model_name` cross-engine remap.

## Success Criteria
* CLI engine selection never loads the wrong model.
* Tests cover cross-engine defaults and pass.

## Related Issues
* Architecture: Engines module in-progress (ARCHITECTURE.md).

---

Issue #2: [BUG] VAD CLI crashes when ffmpeg is missing
Labels: `type:bug`, `area:audio`, `priority:high`, `status:proposed`

## Summary
**What:** `vociferous vad` raises unhandled `FileNotFoundError` when ffmpeg is absent, producing a traceback instead of guidance. 
**Outcome:** VAD surfaces the same friendly ffmpeg-missing message/exit code as `decode`.

## Rationale
### Context
`VADComponent.detect` calls `FfmpegDecoder.decode`; CLI only catches `AudioDecodeError`, not `FileNotFoundError`.
### Why This Approach
* **Primary value:** Avoids crashes; consistent UX with decode.
* **Technical advantage:** Clear failure mode for missing dependency.
* **User impact:** Actionable guidance (“install ffmpeg”) instead of traceback.
* **Operational impact:** Reduced support noise.
### Why Not Alternatives
* Leaving as-is keeps crash; docs alone do not prevent it.
* Wrapping with generic catch hides the root cause.
* **Decision summary:** Catch `FileNotFoundError` and emit decode-style message + exit 2.

## Strategy: Error-handling parity with decode
**One-line description:** Handle missing ffmpeg in VAD CLI/component with user-friendly messaging and non-zero exit.

## Phased Execution Plan
### Phase 1 (Immediate)
**Objective:** Add `FileNotFoundError` handling.
**Affected Areas:**
* `src/cli/commands/vad.py` (or `src/audio/components/vad.py`) — mirror decode’s ffmpeg handling.
**Expected Behavior:** VAD prints install hint and exits 2 when ffmpeg missing.

### Phase 2 (Next Release)
**Objective:** Regression test for missing ffmpeg.
**Affected Areas:**
* `tests/audio/test_vad_contract.py` — subprocess with PATH cleared to simulate missing ffmpeg.
**Expected Output:** Non-zero exit; stderr contains guidance; no traceback.

## Decisions Required
1. Catch at CLI vs component? (Recommend CLI for UX parity.)
2. Match decode message verbatim? (Recommend yes.)

## Implementation Checklist
* [ ] Add `FileNotFoundError` handling with friendly message + Exit 2.
* [ ] Add test simulating missing ffmpeg and asserting message/exit code.

## Testing Strategy
* Subprocess test with ffmpeg absent from PATH; assert stderr guidance and non-zero exit.

## Success Criteria
* No traceback when ffmpeg is missing; users see actionable guidance.

## Related Issues
* Audio components must fail loudly with clear errors (ARCHITECTURE.md).

---

Issue #3: [BUG] `vociferous check` fails when sounddevice is absent (should warn)
Labels: `type:bug`, `area:cli`, `priority:medium`, `status:proposed`

## Summary
**What:** `check` marks missing `sounddevice` as FAIL and exits 1, implying broken install even when users only need file-based transcription. 
**Outcome:** Missing `sounddevice` is a warning; command exits success unless critical deps (ffmpeg) are missing.

## Rationale
### Context
Mic capture is optional per architecture; current logic flips `ok` to False when `sounddevice` is missing.
### Why This Approach
* **Primary value:** Avoids false-negative install checks for non-mic users.
* **Technical advantage:** Aligns status with dependency criticality.
* **User impact:** `check` passes when only optional mic support is absent.
* **Operational impact:** Reduces unnecessary install friction.
### Why Not Alternatives
* Keeping failure forces optional dependency installation.
* Silent ignore would hide the limitation; warning is clearer.
* **Decision summary:** Downgrade to WARN without failing overall status.

## Strategy: Optional-dep warning
**One-line description:** Treat missing `sounddevice` as a warning; retain failure only for critical deps.

## Phased Execution Plan
### Phase 1 (Immediate)
**Objective:** Adjust `check` status handling.
**Affected Areas:**
* `src/cli/main.py` (`check`) — do not set `ok = False` for missing sounddevice; clarify mic-disabled note.
**Expected Behavior:** WARN shown for mic; exit code 0 if ffmpeg present.

### Phase 2 (Next Release)
**Objective:** Regression test for optional dep.
**Affected Areas:**
* `tests/cli` — subprocess with sounddevice import blocked; assert exit code 0 and WARN messaging.

## Decisions Required
1. Should warning text explicitly say “mic capture disabled”? (Recommend yes.)
2. Any other optional deps to treat similarly? (Currently none.)

## Implementation Checklist
* [ ] Update `check` to leave `ok` true when only sounddevice is missing; emit WARN with mic-disabled note.
* [ ] Add test asserting exit code 0 and WARN when sounddevice absent, ffmpeg present.

## Testing Strategy
* Subprocess test with sounddevice import blocked; ffmpeg present; assert WARN + success exit.

## Success Criteria
* `check` no longer exits 1 solely due to missing sounddevice; messaging remains clear about mic capture.

## Related Issues
* Aligns with architecture: mic capture is optional, batch workflow is primary (ARCHITECTURE.md).
