# System: Refinement Engine

The **Refinement Engine** is an intelligent post-processing subsystem that transforms raw, verbatim transcription into polished, formatted text. It leverages Small Language Models (SLMs) running locally to understand intent, correct grammar, and apply structural formatting without sacrificing privacy.

<img src="https://raw.githubusercontent.com/WanderingAstronomer/Vociferous/main/docs/images/refinement_view.png" alt="Refinement View" width="800" />

## Architecture

The engine is built on high-performance inference libraries optimized for consumer hardware.

*   **Core Engine**: [CTranslate2](https://github.com/OpenNMT/CTranslate2) (C++ inference engine).
*   **Model Architecture**: Qwen-based (default `qwen4b`) quantized to **Int8** or **Int8_Float16**.
*   **Tokenizer**: HuggingFace `tokenizers`.
*   **Service Layer**: `SLMRuntime` — a lightweight runtime which runs inference via background tasks (no dedicated background thread).  Provisioning/downloads/conversion are NOT performed by the runtime; use `scripts/provision_models.py` or provisioning utilities.

### Performance Optimization
*   **Dynamic Padding**: Output token limits are calculated dynamically based on input length (`input * 0.5 + 150`), capped at 16k tokens, ensuring efficient GPU usage.
*   **Compute Types**: Automatically selects `int8_float16` for CUDA (using Tensor Cores) and `int8` for CPU.

---

## Refinement Levels

The system offers 5 distinct levels of intervention, defined by specific few-shot examples injected into the prompt context.

### Level 0: Literal (Format Only)
*   **Goal**: Fix typos and capitalization ONLY.
*   **Touch**: Minimal. Preserves stutters ("um", "uh") and original phrasing exactly.
*   **Use Case**: Verbatim logging, legal transcription.

### Level 1: Structural (Default)
*   **Goal**: Readable but faithful.
*   **Touch**: Removes dysfluencies (stutters, false starts). Fixes basic punctuation.
*   **Invariant**: Does NOT change the words used, only the flow.

### Level 2: Neutral
*   **Goal**: Standard written English.
*   **Touch**: Smooths out run-on sentences. Corrects grammatical errors.
*   **Use Case**: Email drafts, casual notes.

### Level 3: Intent
*   **Goal**: Professional polish.
*   **Touch**: High. Rephrases awkward constructions for clarity. Prioritizes the *intent* of the user over the specific syntax used.
*   **Use Case**: Documentation, formal requests.

### Level 4: Overkill (Academic/Formal)
*   **Goal**: Maximum density and sophistication.
*   **Touch**: Extreme. Expands vocabulary, structures complex arguments, and adopts a formal tone.
*   **Use Case**: Papers, technical writing, "consultant speak".

---

## Technical Implementation

### Chain-of-Thought ("Thinking")
The engine supports **Reasoning Models**. Output is parsed to separate internal monologue from the final result.
*   **Tag Parsing**: Detects and extracts content within `<think>...</think>` blocks.
*   **Usage**: Prevents reasoning traces from polluting the user's transcript while allowing the model to "plan" its edits.

### Prompt Strategy
Prompts are constructed using the **ChatML** format (or Llama 3 equivalent) with a strict template:

1.  **System Prompt**: Identity and global invariants.
2.  **Few-Shot Examples**: 1-2 examples of Input -> Output behavior specific to the selected Level.
3.  **User Input**: Wrapper in `<<<BEGIN TRANSCRIPT>>>` delimiters to prevent instruction injection attacks.

### Lifecycle Management
The `SLMRuntime` is intentionally focused: it is responsible for loading already-provisioned models from disk, warming the inference engine, running refinements, and managing its enable/disable lifecycle. It does NOT perform provisioning (downloading or format conversion) or device-choice user interactions. Those responsibilities are performed by separate provisioning tooling (e.g., `scripts/provision_models.py`) or manual setup steps.

If an application needs provisioning or conversion, it should be implemented as an explicit provisioning step or separate `ProvisioningManager` service rather than being embedded into the runtime. This separation simplifies the runtime's lifecycle and reduces accidental side-effects in the UI.
