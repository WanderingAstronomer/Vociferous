# Vociferous Architecture Review - Issue Tracker

## Batch 1: Critical Priority - Documentation Updates (Issues #1-4)

This document tracks the GitHub issues created from the architecture review. These issue templates are located in `.github/ISSUE_TEMPLATE/`.

### Status Legend
- 🔴 Not Started
- 🟡 In Progress
- 🟢 Complete

---

## Issue #1: [UPDATE] Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design
**Status:** 🔴 Not Started  
**Labels:** `documentation`, `architecture`, `high-priority`  
**Template:** `.github/ISSUE_TEMPLATE/01-rewrite-architecture-md.md`

### Key Changes
1. Remove over-engineered components (SegmentArbiter, TranscriptionSession)
2. Update Canary-Qwen dual-pass architecture documentation
3. Clarify batch vs streaming processing
4. Fix terminology (Submodule → Utility)
5. Add comprehensive module documentation (all 9 modules)
6. Fix Single Responsibility table
7. Add Artifact Management section
8. Update architecture diagram
9. Update test organization diagram
10. Add user help vs dev help documentation

### Blocks
- #5 (Delete SegmentArbiter)
- #6 (Delete TranscriptionSession)
- #8 (Rename polish module)

### Related
- #2 (Add module architecture documentation)
- #3 (Document help flags)

---

## Issue #2: [UPDATE] Add module architecture documentation
**Status:** 🔴 Not Started  
**Labels:** `documentation`, `architecture`  
**Template:** `.github/ISSUE_TEMPLATE/02-add-module-architecture-docs.md`

### Key Changes
1. Formally define "Module"
2. Create comprehensive module table for all 9 modules
3. Document module boundaries and interactions
4. Clarify infrastructure vs components distinction

### Module List
- `audio` - Audio preprocessing (Components: decode, vad, condense, record)
- `engines` - Speech-to-text transcription (Infrastructure only)
- `refinement` - Text post-processing (Components: refine)
- `cli` - Command-line interface
- `app` - Workflow orchestration
- `config` - Configuration management
- `domain` - Core types and contracts
- `sources` - Audio input sources
- `gui` - Graphical interface

### Part Of
- #1 (Rewrite ARCHITECTURE.md)

### Related
- #8 (Rename polish to refinement)

---

## Issue #3: [CREATE] Document user help vs dev help CLI flag structure
**Status:** 🔴 Not Started  
**Labels:** `documentation`, `enhancement`, `cli`  
**Template:** `.github/ISSUE_TEMPLATE/03-document-help-flags.md`

### Key Changes
1. Document two-tier help system in ARCHITECTURE.md
2. Add help flag examples to README.md
3. Define what goes in `--help` vs `--dev-help`

### User Help (`--help`)
- `transcribe` - Main workflow
- `languages` - List supported languages
- `check` - Verify prerequisites

### Developer Help (`--dev-help`)
- `decode` - Audio normalization
- `vad` - Speech boundary detection
- `condense` - Silence removal
- `refine` - Grammar/punctuation refinement
- `record` - Microphone capture
- All other internal components

### Part Of
- #1 (Rewrite ARCHITECTURE.md)

### Blocks
- #15 (Implement help flag system - code implementation)

---

## Issue #4: [UPDATE] README.md - Remove streaming interface references
**Status:** 🔴 Not Started  
**Labels:** `documentation`, `bug`, `architecture`  
**Template:** `.github/ISSUE_TEMPLATE/04-remove-streaming-references.md`

### Key Changes
1. Remove streaming interface terminology
2. Document batch processing interface
3. Clarify preprocessing pipeline stages
4. Update engine descriptions
5. Add rationale for batch processing

### Files to Update
- `README.md` (line 27 and related sections)
- `docs/ENGINE_BATCH_INTERFACE.md` (if contradictory)

### Related
- #1 (Rewrite ARCHITECTURE.md - batch vs streaming section)
- #21 (Standardize engine interface to batch-only - code changes)

---

## Summary Statistics

- **Total Issues:** 4
- **Documentation Issues:** 4
- **Code Issues:** 0
- **Not Started:** 4 🔴
- **In Progress:** 0 🟡
- **Complete:** 0 🟢

## Next Steps

1. Create these issues in GitHub using one of the methods in `.github/ISSUE_TEMPLATE/README.md`
2. Prioritize Issue #1 as it's the most comprehensive
3. Issue #2 and #3 can be done as part of Issue #1 or separately
4. Issue #4 should be done after Issue #1 to ensure consistency

## Creating Issues via GitHub CLI

```bash
# Navigate to repository root
cd /path/to/Vociferous

# Create all 4 issues at once
for i in {1..4}; do
  case $i in
    1)
      gh issue create \
        --title "[UPDATE] Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design" \
        --body-file .github/ISSUE_TEMPLATE/01-rewrite-architecture-md.md \
        --label "documentation,architecture,high-priority"
      ;;
    2)
      gh issue create \
        --title "[UPDATE] Add module architecture documentation" \
        --body-file .github/ISSUE_TEMPLATE/02-add-module-architecture-docs.md \
        --label "documentation,architecture"
      ;;
    3)
      gh issue create \
        --title "[CREATE] Document user help vs dev help CLI flag structure" \
        --body-file .github/ISSUE_TEMPLATE/03-document-help-flags.md \
        --label "documentation,enhancement,cli"
      ;;
    4)
      gh issue create \
        --title "[UPDATE] README.md - Remove streaming interface references" \
        --body-file .github/ISSUE_TEMPLATE/04-remove-streaming-references.md \
        --label "documentation,bug,architecture"
      ;;
  esac
done
```

---

**Note:** This is Batch 1 of 6. Additional issue batches will be created as separate tracking documents.
