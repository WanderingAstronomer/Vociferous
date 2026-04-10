"""
CPU Refinement Benchmark Harness — Phase 0 of the CPU Speedup Plan.

Measures refinement latency, token throughput, and CPU utilization across
thread counts and transcript lengths. Outputs structured CSV for analysis.

Usage:
    python -m scripts.refinement_benchmark
    python -m scripts.refinement_benchmark --threads 1 2 4 8
    python -m scripts.refinement_benchmark --corpus scripts/benchmark_corpus.json
    python -m scripts.refinement_benchmark --runs 3 --threads 4 8 --bucket short
    python -m scripts.refinement_benchmark --csv results.csv

Requires a provisioned SLM model (run provisioning first).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.model_registry import SLMModel, get_slm_model
from src.core.resource_manager import ResourceManager
from src.core.settings import RefinementSettings, get_settings, init_settings


@dataclass(slots=True)
class BenchmarkResult:
    """One refinement run's measurements."""

    sample_id: str
    bucket: str
    input_words: int
    input_chars: int
    prompt_tokens: int
    max_token_budget: int
    output_tokens: int
    wall_time_s: float
    tokens_per_sec: float
    thread_count: int
    model_id: str
    changed: bool
    run_number: int
    refinement_need_score: float


# ── Helpers ─────────────────────────────────────────────────────────────────


def _resolve_model_dir(model: SLMModel) -> Path:
    """Find the local CT2 model directory."""
    cache_dir = ResourceManager.get_user_cache_dir("models")
    local_dir_name = model.repo.split("/")[-1]
    model_dir = cache_dir / local_dir_name
    if not (model_dir / model.model_file).exists():
        raise FileNotFoundError(
            f"Model not found at {model_dir}. Run provisioning first: python -m src.provisioning.cli provision"
        )
    return model_dir


def _load_engine(model_dir: Path, settings: RefinementSettings, n_threads: int):  # noqa: ANN202
    """Create a RefinementEngine with the given thread count. Forces CPU."""
    from src.refinement.engine import RefinementEngine

    return RefinementEngine(
        model_path=model_dir,
        system_prompt=settings.system_prompt,
        invariants=settings.invariants,
        n_gpu_layers=0,  # Force CPU — this benchmark is CPU-only
        n_threads=n_threads,
        compute_type="int8",
    )


def _load_corpus(corpus_path: Path) -> dict[str, list[dict[str, str]]]:
    """Load the benchmark corpus JSON."""
    with open(corpus_path, encoding="utf-8") as f:
        return json.load(f)


def _count_words(text: str) -> int:
    return len(text.split())


# ── Core benchmark ──────────────────────────────────────────────────────────


def _run_single(
    engine,  # noqa: ANN001
    sample: dict[str, str],
    bucket: str,
    n_threads: int,
    model_id: str,
    run_number: int,
    settings: RefinementSettings,
) -> BenchmarkResult:
    """Run one refinement call and capture all metrics."""
    text = sample["text"]
    sample_id = sample["id"]

    # Score refinement need (Phase 2B signal)
    from src.refinement.skip_check import score_refinement_need

    need_score = score_refinement_need(text)

    # Count prompt tokens (same path the engine uses)
    from src.refinement.prompt_builder import PromptBuilder

    pb = PromptBuilder(system_prompt=engine.system_prompt, invariants=engine.invariants)
    messages = pb.build_refinement_messages(text, "", use_thinking=False)
    chatml_str = PromptBuilder.messages_to_chatml(messages)
    encoded = engine.tokenizer.encode(chatml_str)
    prompt_token_count = len(encoded.tokens)

    max_token_budget = engine._calculate_dynamic_max_tokens(prompt_token_count, use_thinking=False)

    # Run refinement
    t0 = time.perf_counter()
    result = engine.refine(
        text,
        user_instructions="",
        temperature=settings.temperature,
        top_p=settings.top_p,
        top_k=settings.top_k,
        repetition_penalty=settings.repetition_penalty,
        use_thinking=False,
    )
    wall_time = time.perf_counter() - t0

    # Count output tokens
    output_encoded = engine.tokenizer.encode(result.content)
    output_token_count = len(output_encoded.tokens)

    tokens_per_sec = output_token_count / wall_time if wall_time > 0 else 0.0

    return BenchmarkResult(
        sample_id=sample_id,
        bucket=bucket,
        input_words=_count_words(text),
        input_chars=len(text),
        prompt_tokens=prompt_token_count,
        max_token_budget=max_token_budget,
        output_tokens=output_token_count,
        wall_time_s=round(wall_time, 4),
        tokens_per_sec=round(tokens_per_sec, 2),
        thread_count=n_threads,
        model_id=model_id,
        changed=result.content.strip() != text.strip(),
        run_number=run_number,
        refinement_need_score=need_score,
    )


def run_benchmark(
    thread_counts: list[int],
    corpus: dict[str, list[dict[str, str]]],
    buckets: list[str],
    runs_per_sample: int,
    model_id: str,
) -> list[BenchmarkResult]:
    """Execute the full benchmark sweep."""

    settings = get_settings()
    slm_model = get_slm_model(model_id)
    if slm_model is None:
        print(f"ERROR: Unknown model_id '{model_id}'")
        sys.exit(1)

    model_dir = _resolve_model_dir(slm_model)
    ref_settings = settings.refinement

    results: list[BenchmarkResult] = []
    total_runs = sum(len(corpus.get(b, [])) * runs_per_sample for b in buckets) * len(thread_counts)

    print(f"\n{'=' * 70}")
    print(f"  CPU Refinement Benchmark")
    print(f"  Model: {slm_model.name} ({model_id})")
    print(f"  Model path: {model_dir}")
    print(f"  Thread counts: {thread_counts}")
    print(f"  Buckets: {buckets}")
    print(f"  Runs per sample: {runs_per_sample}")
    print(f"  Total refinement calls: {total_runs}")
    print(f"{'=' * 70}\n")

    run_counter = 0

    for n_threads in thread_counts:
        print(f"\n--- Loading engine with n_threads={n_threads} ---")
        load_t0 = time.perf_counter()
        engine = _load_engine(model_dir, ref_settings, n_threads)
        load_time = time.perf_counter() - load_t0
        print(f"    Engine loaded in {load_time:.2f}s")

        for bucket in buckets:
            samples = corpus.get(bucket, [])
            if not samples:
                print(f"    WARNING: No samples in bucket '{bucket}', skipping.")
                continue

            print(f"\n  Bucket: {bucket} ({len(samples)} samples × {runs_per_sample} runs)")

            for sample in samples:
                for run_num in range(1, runs_per_sample + 1):
                    run_counter += 1
                    r = _run_single(engine, sample, bucket, n_threads, model_id, run_num, ref_settings)
                    results.append(r)
                    print(
                        f"    [{run_counter}/{total_runs}] "
                        f"{r.sample_id} run={run_num} "
                        f"| {r.wall_time_s:>6.2f}s "
                        f"| {r.tokens_per_sec:>6.1f} tok/s "
                        f"| in={r.input_words}w/{r.prompt_tokens}tok "
                        f"| out={r.output_tokens}tok "
                        f"| need={r.refinement_need_score:.2f} "
                        f"| changed={r.changed}"
                    )

        # Release engine before loading next thread count
        del engine

    return results


# ── Output ──────────────────────────────────────────────────────────────────


def _print_summary(results: list[BenchmarkResult]) -> None:
    """Print a human-readable summary table."""
    if not results:
        return

    print(f"\n\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")

    # Group by (thread_count, bucket)
    groups: dict[tuple[int, str], list[BenchmarkResult]] = {}
    for r in results:
        key = (r.thread_count, r.bucket)
        groups.setdefault(key, []).append(r)

    header = f"{'Threads':>8} {'Bucket':>8} {'Samples':>8} {'Avg Time':>10} {'Med Time':>10} {'Avg tok/s':>10} {'Avg OutTok':>10}"
    print(header)
    print("-" * len(header))

    for (threads, bucket), group in sorted(groups.items()):
        times = sorted(r.wall_time_s for r in group)
        tps_vals = [r.tokens_per_sec for r in group]
        out_toks = [r.output_tokens for r in group]

        avg_time = sum(times) / len(times)
        median_time = times[len(times) // 2]
        avg_tps = sum(tps_vals) / len(tps_vals)
        avg_out = sum(out_toks) / len(out_toks)

        print(
            f"{threads:>8} {bucket:>8} {len(group):>8} "
            f"{avg_time:>9.3f}s {median_time:>9.3f}s "
            f"{avg_tps:>10.1f} {avg_out:>10.0f}"
        )


def _write_csv(results: list[BenchmarkResult], path: Path) -> None:
    """Write results to CSV."""
    fieldnames = [
        "sample_id",
        "bucket",
        "run_number",
        "thread_count",
        "model_id",
        "input_words",
        "input_chars",
        "prompt_tokens",
        "max_token_budget",
        "output_tokens",
        "wall_time_s",
        "tokens_per_sec",
        "changed",
        "refinement_need_score",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "sample_id": r.sample_id,
                    "bucket": r.bucket,
                    "run_number": r.run_number,
                    "thread_count": r.thread_count,
                    "model_id": r.model_id,
                    "input_words": r.input_words,
                    "input_chars": r.input_chars,
                    "prompt_tokens": r.prompt_tokens,
                    "max_token_budget": r.max_token_budget,
                    "output_tokens": r.output_tokens,
                    "wall_time_s": r.wall_time_s,
                    "tokens_per_sec": r.tokens_per_sec,
                    "changed": r.changed,
                    "refinement_need_score": r.refinement_need_score,
                }
            )
    print(f"\nResults written to {path}")


# ── CLI ─────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CPU Refinement Benchmark — Phase 0 of the CPU Speedup Plan.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--threads",
        type=int,
        nargs="+",
        default=[1, 2, 4, 8],
        help="Thread counts to benchmark (default: 1 2 4 8).",
    )
    parser.add_argument(
        "--corpus",
        type=str,
        default=str(ROOT / "scripts" / "benchmark_corpus.json"),
        help="Path to benchmark corpus JSON.",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        nargs="+",
        default=["short", "medium", "long"],
        help="Transcript buckets to run (default: short medium long).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of runs per sample (for variance measurement). Default: 1.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="",
        help="SLM model ID to benchmark. Default: use settings.",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="",
        help="Output CSV file path. Default: print to stdout only.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    # Force CPU-only for benchmarking
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

    init_settings()
    settings = get_settings()

    model_id = args.model or settings.refinement.model_id
    corpus_path = Path(args.corpus)

    if not corpus_path.exists():
        print(f"ERROR: Corpus file not found: {corpus_path}")
        return 1

    corpus = _load_corpus(corpus_path)

    # Validate buckets exist in corpus
    for b in args.bucket:
        if b not in corpus:
            print(f"ERROR: Bucket '{b}' not found in corpus. Available: {list(corpus.keys())}")
            return 1

    results = run_benchmark(
        thread_counts=sorted(args.threads),
        corpus=corpus,
        buckets=args.bucket,
        runs_per_sample=args.runs,
        model_id=model_id,
    )

    _print_summary(results)

    if args.csv:
        _write_csv(results, Path(args.csv))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
