# Batch 1 Issue Templates - Implementation Summary

## What Was Created

This PR adds GitHub issue templates for **Batch 1** of the Vociferous architecture documentation review. These templates enable creation of 4 critical priority issues focused on updating documentation to match the actual architecture.

## Files Added

### Issue Templates
1. **`.github/ISSUE_TEMPLATE/01-rewrite-architecture-md.md`**
   - Issue #1: Comprehensive rewrite of ARCHITECTURE.md
   - 10 major changes covering architecture, terminology, diagrams, and documentation
   - Labels: `documentation`, `architecture`, `high-priority`

2. **`.github/ISSUE_TEMPLATE/02-add-module-architecture-docs.md`**
   - Issue #2: Add comprehensive module architecture documentation
   - Documents all 9 modules with purposes and responsibilities
   - Labels: `documentation`, `architecture`

3. **`.github/ISSUE_TEMPLATE/03-document-help-flags.md`**
   - Issue #3: Document two-tier help system (--help vs --dev-help)
   - Separates user-facing from developer commands
   - Labels: `documentation`, `enhancement`, `cli`

4. **`.github/ISSUE_TEMPLATE/04-remove-streaming-references.md`**
   - Issue #4: Remove streaming interface references from README.md
   - Fixes contradictions with batch processing architecture
   - Labels: `documentation`, `bug`, `architecture`

### Supporting Files
5. **`.github/ISSUE_TEMPLATE/README.md`**
   - Comprehensive guide on how to use the templates
   - Includes GitHub CLI commands for automation
   - Documents issue dependencies and priority order

6. **`.github/ISSUE_TEMPLATE/config.yml`**
   - GitHub UI configuration for issue templates
   - Enables proper display in "New Issue" interface

7. **`ISSUES_BATCH_1.md`**
   - Issue tracker document with status tracking
   - Includes summary statistics and next steps
   - Documents relationships between issues

8. **`create_batch1_issues.sh`**
   - Automated bash script to create all 4 issues at once
   - Uses GitHub CLI (gh) for automation
   - Provides success confirmation and links

## How to Use

### Option 1: Automated Creation (Recommended)
```bash
# Make sure gh CLI is installed and authenticated
gh auth login

# Run the automated script
./create_batch1_issues.sh
```

This will create all 4 issues in sequence and display their URLs.

### Option 2: Manual Creation via GitHub CLI
```bash
# Create Issue #1
gh issue create \
  --title "[UPDATE] Rewrite ARCHITECTURE.md to reflect Canary-Qwen dual-pass design" \
  --body-file .github/ISSUE_TEMPLATE/01-rewrite-architecture-md.md \
  --label "documentation,architecture,high-priority"

# Create Issue #2
gh issue create \
  --title "[UPDATE] Add module architecture documentation" \
  --body-file .github/ISSUE_TEMPLATE/02-add-module-architecture-docs.md \
  --label "documentation,architecture"

# Create Issue #3
gh issue create \
  --title "[CREATE] Document user help vs dev help CLI flag structure" \
  --body-file .github/ISSUE_TEMPLATE/03-document-help-flags.md \
  --label "documentation,enhancement,cli"

# Create Issue #4
gh issue create \
  --title "[UPDATE] README.md - Remove streaming interface references" \
  --body-file .github/ISSUE_TEMPLATE/04-remove-streaming-references.md \
  --label "documentation,bug,architecture"
```

### Option 3: GitHub Web Interface
1. Go to the repository on GitHub
2. Navigate to the "Issues" tab
3. Click "New Issue"
4. Select the appropriate template from the list
5. Review and submit

## Issue Priorities

All issues in Batch 1 are marked as **Critical Priority** because they address fundamental documentation inaccuracies.

**Recommended implementation order:**
1. **Issue #1** (Comprehensive ARCHITECTURE.md rewrite) - Do this first
2. **Issue #2** (Module documentation) - Can be part of #1 or separate
3. **Issue #3** (Help flag documentation) - Quick documentation-only task
4. **Issue #4** (README.md streaming fixes) - Fixes contradictions

## Issue Dependencies

```
Issue #1 (ARCHITECTURE.md rewrite)
  ├─ Blocks: #5 (Delete SegmentArbiter)
  ├─ Blocks: #6 (Delete TranscriptionSession)
  ├─ Blocks: #8 (Rename polish module)
  ├─ Includes: #2 (Module documentation)
  └─ Includes: #3 (Help flag docs)

Issue #2 (Module documentation)
  └─ Part of: #1
  
Issue #3 (Help flag documentation)
  ├─ Part of: #1
  └─ Blocks: #15 (Implement help flags - code)

Issue #4 (README.md fixes)
  ├─ Related: #1 (batch vs streaming)
  └─ Related: #21 (Batch interface refactoring - code)
```

## What These Issues Address

### Key Problems Identified
1. **SegmentArbiter** and **TranscriptionSession** references in docs (being removed from codebase)
2. **"Polisher"** terminology (should be "Refiner")
3. **Streaming interface** documentation (contradicts batch processing architecture)
4. **Missing module documentation** (7 of 9 modules not documented)
5. **Unclear help system** (no distinction between user and developer commands)
6. **Outdated diagrams** (don't reflect current architecture)
7. **"Submodule"** terminology (should be "Utility")

### What Will Be Fixed
- ✅ Accurate Canary-Qwen dual-pass architecture documentation
- ✅ Clear batch processing explanation and rationale
- ✅ Complete module documentation (all 9 modules)
- ✅ Consistent terminology throughout
- ✅ Updated architecture diagrams
- ✅ Two-tier help system documentation
- ✅ No contradictions between README and ARCHITECTURE.md

## Testing Templates

To verify the templates are properly formatted:

```bash
# View a template
cat .github/ISSUE_TEMPLATE/01-rewrite-architecture-md.md

# Check YAML frontmatter
head -n 7 .github/ISSUE_TEMPLATE/01-rewrite-architecture-md.md

# Validate with gh CLI (dry run)
gh issue create --body-file .github/ISSUE_TEMPLATE/01-rewrite-architecture-md.md --web
```

## Next Steps After Creating Issues

1. ✅ Create all 4 issues using one of the methods above
2. ✅ Start with Issue #1 (highest priority, most comprehensive)
3. ✅ Use `ISSUES_BATCH_1.md` to track progress
4. ✅ Update issue status as work progresses
5. ✅ Cross-reference related issues and PRs

## Notes

- All issues in Batch 1 are **documentation-only** changes
- No code changes are required for these issues
- Subsequent batches will include code refactoring issues
- Each issue has detailed success criteria and related issues documented
- Templates follow GitHub issue template best practices with YAML frontmatter

## Questions or Issues?

If you encounter any problems with the templates:
1. Check `.github/ISSUE_TEMPLATE/README.md` for detailed instructions
2. Verify `gh` CLI is installed and authenticated
3. Ensure you have write access to the repository
4. Review `ISSUES_BATCH_1.md` for issue relationships

---

**Created:** 2025-12-10  
**Batch:** 1 of 6  
**Type:** Documentation Updates (Critical Priority)  
**Issues:** #1, #2, #3, #4
