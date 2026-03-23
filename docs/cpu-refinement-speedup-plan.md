# CPU-Only Refinement Speedup Plan

**Date:** 2026-03-23  
**Status:** Planning  
**Scope:** Speed up the refinement feature on CPU-only systems without violating Vociferous' single-user desktop responsiveness.

## Why this document exists

The current refinement path already does a few sane things:

- CPU inference uses CTranslate2 `intra_threads` via `refinement.n_threads` (`src/refinement/engine.py`, `src/core/settings.py`)
- the SLM runtime serializes inference behind one lock (`src/services/slm_runtime.py`)
- refinement defaults to `/no_think`, which avoids wasting tokens on pointless reasoning for grammar cleanup (`src/refinement/prompt_builder.py`, `src/services/slm_runtime.py`)

That is a decent starting point, but it is not a speed plan. It is just a pile of defaults that happen to be less stupid than the alternatives.

This document turns the research notes for CPU-only acceleration into an execution order with gates, success metrics, and explicit "do not touch this yet" calls.

## Non-negotiable constraints

1. **Do not block the UI thread or the API loop.**
2. **Do not make refinement throughput faster by making the desktop feel worse.**
3. **Do not ship speculative complexity before measuring the current bottleneck.**
4. **Do not assume throughput improvements help single-request latency.** Those are related, but they are not the same damn thing.

## Success metrics

Measure all experiments on the same corpus slice and hardware profile.

- **Time to first visible improvement** in the UI
- **End-to-end refinement latency** for short, medium, and long transcripts
- **Tokens per second** during SLM generation
- **CPU utilization by core**
- **Peak RAM usage**
- **UI responsiveness while refinement runs** (no input lag, no frozen window)

Recommended benchmark buckets:

- **Short:** 25-75 words
- **Medium:** 150-300 words
- **Long:** 500-900 words

## What the codebase says right now

### Current strengths

- `RefinementEngine` already routes CPU inference through `intra_threads=n_threads`, which means thread tuning is a real knob, not wishful thinking.
- `SLMRuntime` holds a single engine behind a lock, which prevents concurrent CPU refinements from dogpiling the machine.
- The prompt path already supports `use_thinking=False`, which is the correct default for mechanical cleanup work.

### Current limits

- There is **no benchmark harness** for refinement latency.
- There is **no autotuning** for CPU thread count.
- There is **no confidence gate** to avoid sending obviously clean text through the SLM.
- The runtime is built for **single-request latency**, not ensemble decoding or parallel refinement experiments.

## Recommended plan

### Phase 0 — Measure the real bottleneck first

**Goal:** Stop guessing.

#### Benchmarking tasks

1. Extend the existing `scripts/refinement_probe.py` workflow into a repeatable CPU benchmark routine.
2. Capture:
   - transcript length
   - prompt token count
   - max token budget
   - total wall time
   - output token count
   - tokens/sec
   - thread count
   - model ID
3. Run the same sample set across `n_threads = 1, 2, 4, 8, 12, 16` on representative CPUs.

#### Success gate

Do not change defaults until the benchmark shows where latency actually bends or plateaus.

#### Why this comes first

Because "optimize" without numbers is how people end up building an expensive shrine to the wrong bottleneck.

### Phase 1 — Ship the boring wins first

These are the highest-confidence changes because they fit the current architecture instead of fighting it.

### 1A. Thread-count tuning and sane presets

**Recommendation:** Highest priority for direct CPU-only refinement speed.

- Benchmark the current `n_threads` behavior and set a better default for CPU mode.
- Add platform guidance such as:
  - 4-core CPU: start at 2-3 threads
  - 8-core CPU: start at 4-6 threads
  - 12-16 core CPU: start at 6-10 threads
- Consider an **"Auto"** mode later, but only if it is conservative and based on physical cores rather than every logical thread the OS can scream about.

**Why it is viable:** The knob already exists in code and UI. This is a calibration problem, not an architecture rewrite.

### 1B. Reduce wasted generation budget

**Recommendation:** High priority.

- Audit `_calculate_dynamic_max_tokens()` for CPU cleanup workloads.
- Validate whether the current fixed padding and thinking reserve are too generous for short/medium transcripts.
- If benchmarks confirm over-generation headroom, clamp the output budget more aggressively for literal cleanup mode.

**Why it is viable:** Smaller generation budgets cut CPU work directly. If the model only needs a butter knife, stop handing it a flamethrower.

### 1C. Fast-path obvious no-op cases

**Recommendation:** Medium priority.

- Skip refinement for empty, whitespace-only, or trivially short transcripts where the SLM adds no value.
- Evaluate a cheap pre-check for already-clean text before dispatching the model.

**Why it is viable:** The fastest refinement call is the one you never make.

### Phase 2 — Reduce how often full refinement is needed

This is where the issue gets more interesting. Instead of making every refinement call faster, reduce the number of transcripts that need expensive full-pass cleanup.

### 2A. Confidence-aware editing

**Recommendation:** Highest product-value follow-up after Phase 1.

- Surface low-confidence ASR regions inline.
- Offer top-N alternatives only for weak tokens or spans.
- Let the user fix the ugly parts before the SLM ever runs.

**Why it is viable:** This uses existing decoder signal instead of paying for a second model pass everywhere.

**Important distinction:** This is mostly a **work reduction** strategy, not a raw decoder speedup. That still counts, because users care about elapsed time, not your philosophical purity.

### 2B. Confidence-gated refinement routing

**Recommendation:** Medium priority.

- Define a threshold where clean, high-confidence transcripts stay on the cheap path.
- Reserve full refinement for transcripts with:
  - many low-confidence spans
  - high filler density
  - obvious formatting damage

**Why it is viable:** CPU-only systems benefit more from selective refinement than from brute-force everything-all-the-time behavior.

### Phase 3 — Improve perceived latency, not just raw refinement speed

These items matter, but they are not the same problem.

### 3A. Streaming transcription

**Recommendation:** High priority for product latency, separate epic for engineering scope.

- Stream ASR output as chunks arrive.
- Keep the editor warm with incremental text rather than making the user wait for one giant reveal.
- Use pause windows for background cleanup or candidate generation.

**Why it matters:** Even if final refinement time barely changes, the product feels dramatically faster because users see text while they speak.

**Why it is not Phase 1:** This is broader than refinement. It touches ASR flow, UI timing, and event plumbing. Worth doing. Not a "quick speedup."

### 3B. Pause-window background work

**Recommendation:** Medium priority after streaming exists.

- Spend idle CPU during speech pauses on cheap predictive work:
  - n-gram suggestions
  - confidence rescoring
  - candidate preparation for low-confidence spans

**Why it matters:** It steals work from the end of the pipeline and moves it into natural idle gaps.

### Phase 4 — Personalization experiments

### 4A. Corpus-backed n-gram cache

**Recommendation:** Experimental, gated by corpus analysis.

- Mine the user's SQLite corpus for top unigram/bigram/trigram transitions.
- Measure:
  - Zipfian coefficient
  - top-50 and top-100 coverage
  - phrase recurrence across sessions
- Use this only in pause windows or as a lightweight suggester.

**Why it might work:** Personalized text is often repetitive in exactly the boring ways that statistics can exploit.

**Why it is not a first move:** It is data-dependent. If the corpus does not show strong coverage, this turns into clever garbage.

## Explicitly deferred: int4 ensemble voting

**Recommendation:** Do not build this now.

### Why it is attractive

- In theory, several cheap passes could beat one expensive pass.

### Why it is currently a bad bet

- `SLMRuntime` is intentionally serialized behind one engine lock.
- CPU-only desktop apps care about **single-request latency** and responsiveness, not just aggregate throughput.
- Int4 quality and kernel maturity are less proven than int8 for this use case.
- Python-side token voting would be its own fresh pile of overhead.
- A native aggregation kernel would be required before this stops being academic cosplay.

### Gate

Only revisit this if all of the following are true:

1. int4 coherence is measured on a real corpus slice
2. the per-pass quality drop is acceptable
3. a native aggregation path exists
4. the machine still stays responsive under parallel load

Until then, this idea belongs in the parking lot, not on the sprint board.

## Priority order

1. **Benchmark harness and corpus slice**
2. **Thread-count tuning**
3. **Generation-budget trimming**
4. **No-op / short-text fast path**
5. **Confidence-aware editing**
6. **Confidence-gated refinement routing**
7. **Streaming transcription**
8. **Pause-window background prediction**
9. **Corpus-backed n-gram cache**
10. **Int4 ensemble voting only if every gate passes**

## Suggested deliverables

### Milestone A — Evidence

- Benchmark results for CPU refinement on at least one short, medium, and long transcript set
- Recommended `n_threads` ranges by core count
- Evidence for whether token-budget trimming helps or hurts output quality

### Milestone B — Cheap wins

- Updated CPU-thread defaults or guidance
- Reduced generation budget where safe
- Fast-path skips for transcripts that do not merit SLM work

### Milestone C — Reduced work

- Confidence-aware inline editing design
- Confidence-gated routing rules

### Milestone D — Broader latency work

- Streaming ASR plan
- Pause-window prediction plan
- Corpus-statistics report

## External validation worth keeping in mind

- Faster-Whisper's published benchmarks show that **int8 on CPU is already the sane default**, and batching improves throughput at the cost of more RAM, which matters for offline desktop apps.  
  Source: https://github.com/SYSTRAN/faster-whisper
- Current CTranslate2 guidance and ecosystem reporting consistently treat **int8 as the mature CPU path**, while lower-bit quantization needs workload-specific validation before anyone should trust it with quality-sensitive text cleanup.  
  Sources: https://opennmt.net/CTranslate2/quantization.html, https://pypi.org/project/faster-whisper/

## Bottom line

The viable plan is not "throw int4 at the wall and pray."

The viable plan is:

1. measure the current CPU path,
2. tune the knobs that already exist,
3. reduce wasted generation,
4. avoid unnecessary refinement calls,
5. then tackle larger latency wins like streaming and confidence-aware editing.

That order is boring. Good. Boring is how you get real speedups without turning the refinement stack into an unmaintainable science fair project.
