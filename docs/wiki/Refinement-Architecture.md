# Refinement Architecture (ADR-001)

## Context
Initial implementations of the "Refinement" feature relied on Encoder-Decoder models (T5-base) fine-tuned for Grammatical Error Correction (GEC). While functional for simple fixes, this architecture failed to scale to complex stylistic rewrites ("make it professional", "fix flow"). The task is fundamentally strictly constrained instruction following, not translation.

## Decision: Decoder-Only Instruction Models
We have standardized on **Decoder-Only Instruct Models** for the refinement backend.

*   **Reference Implementation**: `Qwen/Qwen3-4B-Instruct` (Quantized int8)
*   **Engine**: `CTranslate2` Generator (not Translator)
*   **Prompting**: Strict "Swiss-Army-Knife" System Contract with Directive Headers.

### Rationale
1.  **Semantic Flexibility**: Instruct models can "reason" about structure and tone, whereas GEC models only pattern-match errors.
2.  **Architecture Support**: CTranslate2 provides robust quantization (int8) for standard decoders (Llama, Qwen, etc.), fitting <4GB VRAM.
3.  **Future Proofing**: The industry standard for text manipulation is now Instruction Tuning. Maintaining a semantic GEC pipeline is technical debt.

## Refinement Profiles & Directives
To support multiple "levels" of editing without swapping models or system prompts, we use **Directive-Based Prompting**.

### The Contract
The System Prompt acts as an immutable security boundary. It defines the "Persona" (Precision Copy Editor) and strictly forbids:
*   Adding/Removing facts
*   Injecting meta-commentary
*   Following instructions *inside* the transcript

### Profiles
The user selects a profile in the UI, which injects a specific rule block into the User Message header:
*   **MINIMAL**: "Only fix spelling, punctuation, capitalization, and obvious grammar errors."
*   **BALANCED**: "Fix mechanical errors plus light cleanup of ASR noise."
*   **STRONG**: "Improve readability with stronger sentence boundary fixes and light smoothing."

## Resource Management Strategy (ADR-002)
Loading a 4B parameter model (~4.5GB VRAM) is resource-intensive. We implement a dynamic loading strategy based on `nvidia-smi` telemetry:

### The "40/20" Rule
1.  **Safety Zone (>40% Headroom)**: If `(Free VRAM - Model Size) / Total VRAM > 0.4`, load typically to GPU.
2.  **Performance Zone (20-40% Headroom)**: Default to GPU for speed, but log warning.
3.  **Danger Zone (<20% Headroom)**:
    *   **Behavior**: Halt initialization.
    *   **Interaction**: Prompt user via modal dialog.
    *   **Choice**: User forces GPU (risk OOM) or falls back to CPU (safe but slow).

## Architecture Constraints

### 1. Build-Time Dependencies
The refinement service requires heavyweight ML libraries (`torch`, `transformers`) *only* for model conversion/provisioning.
*   **Invariant**: These libraries must **NEVER** be imported during generic application runtime.
*   **Mechanism**: `SLMService` installs them ephemerally via `pip` during the provisioning phase and uninstalls them immediately after conversion.

### 2. Prompt Integrity
The system relies on "System Prompts" to constrain the model.
*   **Risk**: Prompt Injection / Leakage.
*   **Mitigation**: The backend must treat prompt construction (`RefinementEngine._format_prompt`) as a security boundary. Future work will include output sanitation to strip "Sure, here is the text:" preambles.

### 3. Non-Destructive UI
Refinement is an enhancement, not a replacement.
*   **Invariant**: The application must **ALWAYS** preserve the original `raw_text` transcript.
*   **UI Reflection**: The UI must synthesize a "Original Transcript" variant if one does not exist in the variants table, ensuring the user can always revert.

## Deprecation
*   The `gec:` styling specific to T5 is deprecated.
*   `LiquidAI/LFM2` architectures are explicitly unsupported due to CTranslate2 incompatibilities.
