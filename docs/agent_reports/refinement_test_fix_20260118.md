# Agent Research Journal - Refinement Orchestration Test Fix

## Task Overview
The test `test_mainwindow_owned_engine_orchestration` in `tests/test_refinement_integration.py` was failing due to an `AssertionError`. The test expected `set_loading(True)` to be called immediately upon navigating to the Refinement view.

## System Understanding and Assumptions
Based on the `CHANGELOG.md` and current implementation of `MainWindow._on_refine_view_requested`, the system shifted from an immediate-execution model to a "Draft Mode" model for refinement. 

1. **Previous Behavior**: Requesting a refinement immediately switched to the view and started the backend engine (showing the loading overlay).
2. **Current Behavior**: Requesting a refinement switches to the view in "Draft Mode", loading the data but allowing the user to tweak instructions and profiles before clicking "Refine" to start execution.

## Identified Invariants and Causal Chains
- Invariant: `MainWindow` is the orchestrator for refinement flow.
- Causal Chain: User Request (from Transcribe/History) -> `_on_refine_view_requested` -> View Switch + Data Load -> User Interaction in `RefineView` -> `Refine` Click -> `_on_refinement_execution_requested` -> `set_loading(True)` + `refinement_requested.emit`.

## Decisions Made
- **Retain and Modify Test**: The test is valuable for ensuring `MainWindow` correctly orchestrates the multi-step refinement process. Deleting it would lose coverage of the ingress and execution handoffs.
- **Update Test Expectations**: Updated the test to verify that ingress does *not* set loading to True, and added a step to simulate the execution request where loading *is* expected. Added a third step to verify completion correctly updates the view.

## Trade-offs Considered
- **Splitting the test**: I could have split this into two tests (Ingress vs Execution), but since they are part of a single logical flow owned by the orchestrator, keeping them in one integration test maintains the narrative of the orchestration contract.

## Post-Task Recommendation
This journal reflects the resolution of a regression in the test suite caused by architectural evolution. It should be archived.
