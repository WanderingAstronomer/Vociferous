# Agent Report - Button Focus Artifact Fix

## System Understanding and Assumptions
The `Vociferous` application uses a unified styling system defined in `src/ui/styles/unified_stylesheet.py`. Styling follows modern web-inspired patterns (e.g., using `outline` for focus states) but must remain compatible with Qt's QSS engine and various platform-specific rendering behaviors on Linux.

## Identified Invariants and Causal Chains
- Action buttons (`primaryButton`, `secondaryButton`, `destructiveButton`, `purpleButton`) used the `outline` property for focus indicators.
- `outline` is not a standard QSS property. In some Qt environments (particularly on Linux), this property either enables the default platform focus rectangle (which ignores `border-radius`) or renders an unclipped rectangular border inside/outside the widget.
- The `ConfirmationDialog` explicitly sets focus on the "Delete" button, making the artifact visible immediately upon opening.
- Users reported an "inner rectangular border" on the Delete button, which corresponds exactly to the behavior of a non-standard `outline` property on a rounded button.

## Data Flow and Ownership Reasoning
Styling is central and owned by `unified_stylesheet.py`. All widgets using `styleClass="destructiveButton"` were affected.

## UI Intent -> Execution Mappings
- Focus event on Button -> Qt style engine evaluates `:focus` pseudo-state -> `outline` property causes artifact.

## Decisions Made
1. **Remove Invalid Properties**: All occurrences of `outline: 2px solid ...` and `outline-offset` were removed from `unified_stylesheet.py`.
2. **Standardize Focus Indicators**: Replaced `outline` with standard QSS properties that respect the widget's box model and rounded corners:
    - `destructiveButton`: Focused state now changes `border-color` to `RED_4` (lighter variant).
    - `secondaryButton`: Focused state now matches hover state (`border-color: BLUE_4`, `color: BLUE_3`) for visual priority without ghost borders.
    - `primaryButton`: Focused state now slightly lightens `background-color` to `BLUE_3` (matches hover).
    - `purpleButton`: Focused state now changes `border-color` to `PURPLE_4`.
3. **Preserve Suppression**: Kept `outline: none;` on the base `QPushButton` selector to continue suppressing default platform focus rectangles where supported.

## Post-Task Recommendation
The journal should be archived.
