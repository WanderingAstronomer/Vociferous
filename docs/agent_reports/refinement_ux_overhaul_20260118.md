# Agent Research Journal - Refinement View UX Overhaul

## Task Overview
The goal was to redesign the Refinement controls in `RefineView` (often referred to as the Transcribe view by the user) to treat refinement as a **contextual operation** rather than a set of always-on global controls.

## System Understanding and Assumptions
- **Original Layout**: Footer had Strength Controls (Left), User Input (Center), Rerun Button (Right). This created visual competition and lacked hierarchy.
- **Problem**: Users felt "Decision Pressure" to adjust settings before deciding to refine. The Refine button felt detached from the settings.
- **Mental Model Shift**: Move from "Control Panel" to "Contextual Action Strip".
  - Hierarchy: Content -> Intent -> Parameters.

## Decisions Made
1.  **Refinement Action Strip**: 
    - Moved user input to the left (primary).
    - Grouped Strength Slider and Refine Button into a compact strip on the right.
    - Added microcopy ("Controls how aggressively the text is rewritten") to clarify semantics.
2.  **Visual Subordination**:
    - Strength slider: Muted track styling, smaller label.
    - Refine Button: Accent color only when active (transcript selected and not loading).
    - Used `_update_controls_state` to strictly enforce enabled/disabled visual states based on context (`_current_transcript_id` and `_is_loading`).
3.  **Layout**:
    - Used `QHBoxLayout` for the footer, giving the specific "Action Strip" alignment (BottomRight) to anchor it contextually.

## Trade-offs Considered
- **Input placement**: Moving input to the left makes it the first thing seen in the footer, which aligns with "Intent" (User Instructions).
- **Slider size**: Reduced fixed width to reduce dominance.
- **Microcopy**: Added as a permanent label inside the strip. Considered hiding it, but static explanation is better for clarity.

## Implementation Details
- Modified `src/ui/views/refine_view.py`.
- Replaced the entire footer construction logic in `_setup_ui`.
- Added dynamic state management in `_update_controls_state`.

## Post-Task Recommendation
The `RefineView` now adheres to the "Contextual Tools" design principle. This journal should be archived.
