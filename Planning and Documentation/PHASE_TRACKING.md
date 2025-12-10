# Proper Issue Execution Order

Here's the **dependency-aware execution order** for all 24 issues:

---

## Phase 1: Foundation & Documentation (Do First)

**These have NO dependencies and establish the foundation:**

1. **Issue #1** - [UPDATE] Rewrite ARCHITECTURE.md ⭐ **START HERE**
   - **Why first:** Documents the target architecture, provides reference for all other work
   - **Blocks:** Many other issues reference updated architecture
   - **Effort:** 4-6 hours

2. **Issue #2** - [UPDATE] Add module architecture documentation
   - **Depends on:** #1 (part of architecture update)
   - **Why early:** Clarifies module boundaries before refactoring
   - **Effort:** 2 hours

3. **Issue #3** - [CREATE] Document user help vs dev help
   - **Depends on:** #1 (part of architecture update)
   - **Why early:** Documents design before implementation
   - **Effort:** 1 hour

4. **Issue #4** - [UPDATE] README.md - Remove streaming references
   - **Depends on:** #1 (references architecture)
   - **Why early:** Aligns user-facing docs with architecture
   - **Effort:** 1 hour

5. **Issue #18** - [UPDATE] Add module status to ARCHITECTURE.md header
   - **Depends on:** #1 (part of architecture update)
   - **Why early:** Tracks refactoring progress
   - **Effort:** 1 hour

**Phase 1 Total:  1-2 days**

---

## Phase 2: Critical Architecture Refactoring (Core Changes)

**These are the major refactoring tasks - do before features:**

6. **Issue #5** - [DELETE] Remove SegmentArbiter ⭐ **CRITICAL**
   - **Depends on:** #1 (architecture documents why it's removed)
   - **Blocks:** #7 (transcribe redesign uses this)
   - **Why critical:** Removes over-engineering, simplifies pipeline
   - **Effort:** 3-4 hours

7. **Issue #6** - [REFACTOR] Delete TranscriptionSession ⭐ **CRITICAL**
   - **Depends on:** #1, #5 (architecture changes)
   - **Blocks:** #7 (transcribe redesign replaces session)
   - **Why critical:** Enables transparent workflow
   - **Effort:** 4-5 hours

8. **Issue #9** - [CREATE] Implement Canary-Qwen dual-pass ⭐ **HIGHEST PRIORITY**
   - **Depends on:** #1 (architecture defines Canary design)
   - **Blocks:** #8, #10, #20 (refinement depends on Canary LLM mode)
   - **Why critical:** Core engine change, foundation for refinement
   - **Effort:** 8-12 hours (largest single task)

9. **Issue #7** - [REFACTOR] Redesign `transcribe` command
   - **Depends on:** #5, #6, #9 (uses new workflow without arbiter/session, with Canary)
   - **Blocks:** #16, #17 (flags and cleanup depend on redesigned command)
   - **Why critical:** Main user-facing command, orchestrates everything
   - **Effort:** 4-6 hours

10. **Issue #8** - [RENAME] Rename `polish` to `refinement`
    - **Depends on:** #9 (Canary LLM mode defines what refinement is)
    - **Blocks:** #10 (refine component uses renamed module)
    - **Why now:** Terminology must be correct before new features
    - **Effort:** 3-4 hours

**Phase 2 Total: 3-4 days**

---

## Phase 3: New Features & Components (Build on Refactored Base)

**Add new functionality on the clean architecture:**

11. **Issue #10** - [CREATE] Add `vociferous refine` component
    - **Depends on:** #8, #9 (renamed module + Canary LLM mode)
    - **Why now:** Completes component set for manual chainability
    - **Effort:** 3-4 hours

12. **Issue #15** - [FEATURE] Implement `--help` vs `--dev-help` flags
    - **Depends on:** #3 (documentation), #7 (redesigned CLI)
    - **Why now:** Improves UX, hides complexity from users
    - **Effort:** 3-4 hours

13. **Issue #16** - [FEATURE] Add `--keep-intermediates` flag
    - **Depends on:** #7 (redesigned transcribe command)
    - **Blocks:** #19 (artifact config extends this flag)
    - **Why now:** Enables debugging, supports observable outputs
    - **Effort:** 2-3 hours

14. **Issue #17** - [DELETE] Remove `transcribe-full` and `transcribe-canary`
    - **Depends on:** #7, #9 (main transcribe handles everything now)
    - **Why now:** Cleanup redundant commands after redesign
    - **Effort:** 1-2 hours

**Phase 3 Total: 1. 5-2 days**

---

## Phase 4: Testing Infrastructure (Validate Everything)

**Build robust testing before final cleanup:**

15. **Issue #11** - [REFACTOR] Reorganize tests by module
    - **Depends on:** #2 (module structure documented)
    - **Blocks:** #12, #13, #14 (tests need structure first)
    - **Why now:** Foundation for proper test organization
    - **Effort:** 2-3 hours

16. **Issue #12** - [CREATE] Add test artifact directories
    - **Depends on:** #11 (test structure exists)
    - **Blocks:** #13, #14 (tests use artifacts)
    - **Why now:** Enables observable test outputs
    - **Effort:** 1-2 hours

17. **Issue #13** - [CREATE] Add contract tests for all components
    - **Depends on:** #11, #12 (test structure + artifacts)
    - **Blocks:** #23 (validates components before removing mocks)
    - **Why now:** Proves components work with real files
    - **Effort:** 6-8 hours (comprehensive testing)

18. **Issue #14** - [CREATE] Add full pipeline integration test
    - **Depends on:** #7, #9, #11, #12 (redesigned pipeline + test structure)
    - **Why now:** Proves end-to-end workflow works
    - **Effort:** 2-3 hours

**Phase 4 Total: 1. 5-2 days**

---

## Phase 5: Configuration & Cleanup (Finalize System)

**Polish and standardize:**

19. **Issue #19** - [CREATE] Add artifact cleanup configuration
    - **Depends on:** #16 (extends --keep-intermediates with config)
    - **Why now:** Gives users control over file management
    - **Effort:** 2-3 hours

20. **Issue #20** - [DECISION] Deprecate Whisper/Voxtral as primary
    - **Depends on:** #9 (Canary implemented and working)
    - **Blocks:** #21 (engine standardization applies to all engines)
    - **Why now:** Strategic decision based on working Canary
    - **Effort:** 2-3 hours (documentation + warnings)

21. **Issue #21** - [REFACTOR] Standardize engine interface to batch-only
    - **Depends on:** #9, #20 (Canary working, engine strategy decided)
    - **Blocks:** #24 (removes streaming code)
    - **Why now:** Enforces architecture decision across all engines
    - **Effort:** 4-5 hours

22. **Issue #22** - [UPDATE] Replace "Submodule" with "Utility"
    - **Depends on:** #1 (architecture uses correct terminology)
    - **Why now:** Terminology consistency
    - **Effort:** 1-2 hours (search and replace)

23. **Issue #23** - [CLEANUP] Remove mock-based tests
    - **Depends on:** #13, #14 (contract tests replace mocks)
    - **Blocks:** #24 (part of final cleanup)
    - **Why now:** Enforces testing philosophy
    - **Effort:** 4-6 hours

**Phase 5 Total: 2-3 days**

---

## Phase 6: Final Cleanup (Last Step)

**Clean up everything before declaring done:**

24. **Issue #24** - [CLEANUP] Audit and remove dead code ⭐ **FINAL TASK**
    - **Depends on:** ALL OTHER ISSUES (cleans up after all refactoring)
    - **Why last:** Can only identify dead code after all changes complete
    - **Effort:** 4-6 hours

**Phase 6 Total: 0.5-1 day**