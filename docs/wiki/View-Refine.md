# View: Refine

The **Refine View** provides an AI-powered interface for improving transcription quality. It enables semantic post-processing using locally hosted Small Language Models (SLMs).

<img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/refinement_view.png" alt="Refine View" width="800" />

## Component Hierarchy

The view divides into three functional zones:

1.  **Comparison Area** (Top): Two side-by-side `ContentPanel` widgets.
    *   **Left**: Original transcript (Immutable reference).
    *   **Right**: Refined output (AI suggestion).
2.  **Controls Area** (Bottom):
    *   **Custom Instructions**: Free-form text input for steering the model (e.g., "Make it bullet points").
    *   **Strength Selector**: A specialized widget (`StrengthSelector`) controlling the degree of rewriting.
3.  **Loading Overlay**: A full-view overlay blocking interaction during inference.

---

## Refinement Levels

The **Strength Selector** maps to distinct prompting strategies:

| Value | Internal Profile | Effect |
| :---: | :--- | :--- |
| **0** | `MINIMAL` | Grammar and capitalization fixes only. Preserves phrasing. |
| **1** | `BALANCED` | **(Default)** Improves flow and punctuation while keeping the user's voice. |
| **2** | `STRONG` | Significant restructuring. Fixes run-on sentences and awkward phrasing. |
| **3** | `OVERKILL` | Academic/Formal rewrite. Vocabulary expansion and complex sentence structures. |

---

## Capabilities & Interaction

This view focuses on **Decision Making** (Accept vs. Discard).

### Loading State
When `is_loading` is True:
*   All capabilities are disabled.
*   Overlay is visible.
*   User cannot navigate away via Intent (blocked by modal nature implicitly, though not strictly enforced by view).

### Ready State
| Action | Condition | Behavior |
| :--- | :--- | :--- |
| `REFINE` | Transcript Loaded | Re-runs refinement with current Strength and Instructions. |
| `SAVE` | Refined Text Exists | **Accept**: Commits the refined text to `normalized_text` and returns to History. |
| `DISCARD` | Always | **Cancel**: Discards the AI suggestion and returns to History unchanged. |
| `COPY` | Refined Text Exists | Copies the **refined** text to clipboard. |

---

## Signal Flow

1.  **Orchestrator** (MainWindow) injects the transcript via `load_transcript_by_id(id, original_text)`.
2.  User adjusts settings and clicks **Refine**.
3.  `refinement_rerun_requested(id, profile, instructions)` is emitted.
4.  Orchestrator calls `SLMService`, sets View to **Loading**.
5.  On success, Orchestrator calls `set_comparison(id, original, refined)`.
6.  User clicks **Save** -> `refinement_accepted(id, refined_text)` -> Database Update.

