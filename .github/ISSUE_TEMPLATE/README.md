# GitHub Issue Templates - Batch 1 (Critical Priority)

This directory contains GitHub issue templates for critical documentation updates to the Vociferous repository.

## Issues Overview

These are **Batch 1 of 6** issues focused on architecture documentation updates with high priority.

### Issue #1: [UPDATE] Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design
**File:** `01-rewrite-architecture-md.md`  
**Labels:** `documentation`, `architecture`, `high-priority`

Comprehensive rewrite of ARCHITECTURE.md to:
- Remove over-engineered components (SegmentArbiter, TranscriptionSession)
- Document Canary-Qwen dual-pass architecture correctly
- Clarify batch vs streaming processing model
- Add all 9 modules to documentation
- Update architecture and test organization diagrams

### Issue #2: [UPDATE] Add module architecture documentation
**File:** `02-add-module-architecture-docs.md`  
**Labels:** `documentation`, `architecture`

Add comprehensive module architecture documentation:
- Formally define what constitutes a "module"
- Document all 9 modules (audio, engines, refinement, cli, app, config, domain, sources, gui)
- Clarify which modules contain CLI-accessible components vs infrastructure

### Issue #3: [CREATE] Document user help vs dev help CLI flag structure
**File:** `03-document-help-flags.md`  
**Labels:** `documentation`, `enhancement`, `cli`

Document the two-tier help system:
- `--help` for end users (transcribe, languages, check)
- `--dev-help` for developers (decode, vad, condense, refine, record)
- Add documentation to ARCHITECTURE.md and README.md

### Issue #4: [UPDATE] README.md - Remove streaming interface references
**File:** `04-remove-streaming-references.md`  
**Labels:** `documentation`, `bug`, `architecture`

Fix contradictions in README.md:
- Remove streaming interface references
- Document batch processing interface
- Explain preprocessing pipeline
- Add rationale for batch over streaming

## How to Use These Templates

### Option 1: Using GitHub Web Interface
1. Go to the GitHub repository
2. Click on "Issues" tab
3. Click "New Issue"
4. Select the appropriate template from the list
5. Fill in any additional details
6. Submit the issue

### Option 2: Using GitHub CLI (gh)
```bash
# Create Issue #1
gh issue create --title "[UPDATE] Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design" \
  --body-file .github/ISSUE_TEMPLATE/01-rewrite-architecture-md.md \
  --label "documentation,architecture,high-priority"

# Create Issue #2
gh issue create --title "[UPDATE] Add module architecture documentation" \
  --body-file .github/ISSUE_TEMPLATE/02-add-module-architecture-docs.md \
  --label "documentation,architecture"

# Create Issue #3
gh issue create --title "[CREATE] Document user help vs dev help CLI flag structure" \
  --body-file .github/ISSUE_TEMPLATE/03-document-help-flags.md \
  --label "documentation,enhancement,cli"

# Create Issue #4
gh issue create --title "[UPDATE] README.md - Remove streaming interface references" \
  --body-file .github/ISSUE_TEMPLATE/04-remove-streaming-references.md \
  --label "documentation,bug,architecture"
```

### Option 3: Manual Creation
Copy the content from each template file and create the issues manually through the GitHub web interface.

## Issue Dependencies

- Issue #1 is the primary issue that blocks several others
- Issue #2 is part of Issue #1
- Issue #3 is part of Issue #1 and blocks #15 (implementation)
- Issue #4 is related to Issue #1 and blocks #21 (code refactoring)

## Priority Order

All issues in Batch 1 are **Critical Priority** and should be addressed first before moving to subsequent batches.

Suggested implementation order:
1. Issue #1 (comprehensive rewrite, includes aspects of #2 and #3)
2. Issue #2 (can be done as part of #1 or separately)
3. Issue #3 (documentation-only, should be quick)
4. Issue #4 (fix contradictions in README)

## Notes

- These are all **documentation-only** changes
- No code changes required in Batch 1
- Subsequent batches will include code refactoring issues
- Each issue has detailed success criteria for completion verification
