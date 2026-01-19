# Agent Report - Database Signal Bridge Implementation

## System Understanding and Assumptions
The system requires a centralized way to broadcast database changes to the UI.
A `SignalBridge` QObject will act as this central hub.
It needs to handle both individual changes and high-frequency bulk updates efficiently through a grouping mechanism.

## Identified Invariants and Causal Chains
- Invariant: `raw_text` is immutable. (Mentioned in instructions, but relevant here as we emit changes).
- Causal Chain: Database Mutation -> SignalBridge -> UI Update.
- Grouping: When multiple changes occur within a `signal_group`, only one signal is emitted at the end to prevent UI thrashing.

## Data Flow and Ownership Reasoning
- `SignalBridge` is a singleton, ensuring a single source of truth for database events.
- It uses `EntityChange` dataclass from `src/database/events.py`.
- `is_processing_batch` provides direct feedback to UI about long-running operations.

## UI Intent -> Execution Mappings
- This bridge connects the data layer (Execution) back to the UI (Feedback).

## Trade-offs Considered and Decisions Made
- Chose `QObject` with a singleton pattern similar to `ErrorLogger`.
- `signal_group` uses a stack-based/counter approach for nested groups (though usually only one level is needed).
- `reload_required` logic (IDs > 50) is centralized in the bridge to keep repositories simple.
