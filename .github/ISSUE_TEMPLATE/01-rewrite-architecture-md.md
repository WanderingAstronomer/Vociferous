---
name: "[UPDATE] Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design"
about: "Rewrite ARCHITECTURE.md to fix inaccuracies and document correct dual-pass architecture"
title: "[UPDATE] Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design"
labels: documentation, architecture, high-priority
assignees: ''
---

## Description

The ARCHITECTURE.md file contains several inaccuracies and outdated design decisions that need to be corrected based on our architectural review.

## Changes Required

### 1. Remove over-engineered components
- Delete all references to `SegmentArbiter` (over-engineering, will be removed in separate issue)
- Remove `TranscriptionSession` references (violates manual chainability principle)

### 2. Update Canary-Qwen dual-pass architecture
- Replace "Polisher" with "Refiner" throughout
- Document Canary-Qwen dual-pass design:
  - Pass 1: ASR mode (speech → raw text)
  - Pass 2: LLM mode (raw text → refined text)
  - Model stays loaded between passes (optimization)
- Update data flow diagram to show: `Decoder → VAD → Condenser → Canary ASR → Canary Refiner → Output`

### 3. Clarify batch vs streaming
- Add clear explanation: Batch = complete file in, complete result out
- Explain use case: User submits complete audio files (not continuous streams)
- Document why batch is correct for Vociferous (simpler, matches ML APIs, matches use case)
- Remove any ambiguity about streaming interfaces

### 4. Fix terminology
- Change "Submodule" to "Utility" throughout (already fixed in table, verify elsewhere)
- Ensure consistent use of Module/Component/Utility hierarchy

### 5. Add comprehensive module documentation
- Add all 9 modules to documentation: `audio`, `engines`, `refinement`, `cli`, `app`, `config`, `domain`, `sources`, `gui`
- Create module table with purposes and responsibilities
- Clarify which modules contain CLI-accessible components

### 6. Fix Single Responsibility table
- Remove "Engine" row (it's a module, not a component)
- Add note clarifying engines are infrastructure called by workflows, not CLI components

### 7. Add Artifact Management section
- Document test artifact persistence: `tests/<module>/artifacts/` (files overwritten each run)
- Document user-facing behavior: temp files by default, `--keep-intermediates` flag for debugging
- Document manual component execution: always keeps files

### 8. Update architecture diagram
- Distinguish components (CLI-accessible) from workflow orchestrators
- Show `transcribe` as workflow that calls components internally (dotted lines)
- Show Canary ASR and Refiner as internal (not CLI-accessible)
- Use solid lines for data flow, dotted lines for orchestration

### 9. Update test organization diagram
- Restructure mermaid diagram to show module-based test folders
- Show `tests/audio/`, `tests/engines/`, `tests/refinement/`, `tests/cli/`, `tests/app/`, `tests/gui/`, `tests/integration/`, `tests/samples/`

### 10. Add user help vs dev help documentation
- Document `--help` (user-facing: transcribe, languages, check)
- Document `--dev-help` (developer-facing: decode, vad, condense, refine, record)

## Success Criteria

- [ ] All SegmentArbiter references removed
- [ ] All TranscriptionSession references removed
- [ ] Canary dual-pass architecture documented with diagram
- [ ] Batch vs streaming section rewritten with clear explanations
- [ ] All 9 modules listed and documented
- [ ] "Utility" terminology used consistently (no "Submodule")
- [ ] Single Responsibility table fixed (no "Engine" row)
- [ ] Artifact Management section added
- [ ] Architecture diagram rewritten (components vs workflows)
- [ ] Test organization diagram updated (module-based structure)
- [ ] Help flag system documented

## Related Issues

- Blocks: #5 (Delete SegmentArbiter), #6 (Delete TranscriptionSession), #8 (Rename polish module)
- Related: #2 (Add module architecture documentation), #3 (Document help flags)

## Notes

This will be implemented as a **Pull Request** to update the architecture file. The updated ARCHITECTURE.md has been drafted and is ready for review.
