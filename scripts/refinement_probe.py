from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from src.core.settings import get_settings, init_settings
from src.services.slm_runtime import SLMRuntime

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _wait_ready(runtime: SLMRuntime, timeout_s: int = 180) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        state = runtime.state.value
        if state in {"Ready", "Error", "Disabled"}:
            return state == "Ready"
        time.sleep(0.5)
    return False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe Vociferous refinement behavior.")
    parser.add_argument(
        "--text",
        default="i has two apple and she go to store yesterday",
        help="Input text to refine.",
    )
    parser.add_argument(
        "--instructions",
        default="",
        help="Optional custom instructions.",
    )
    parser.add_argument("--level", type=int, default=0, help="Level value passed through compatibility API.")
    parser.add_argument("--temperature", type=float, default=0.05, help="Sampling temperature.")
    parser.add_argument("--top-p", type=float, default=0.8, help="Top-p sampling.")
    parser.add_argument("--top-k", type=int, default=20, help="Top-k sampling.")
    parser.add_argument(
        "--thinking",
        action="store_true",
        help="Enable thinking mode for direct engine call.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print raw model output (before parser strips <think> blocks).",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    init_settings()
    settings = get_settings()
    print(f"Model ID: {settings.refinement.model_id}")

    runtime = SLMRuntime(settings_provider=get_settings)
    runtime.enable()

    try:
        if not _wait_ready(runtime):
            print(f"Runtime not ready. State: {runtime.state.value}")
            return 1

        print(f"Runtime State: {runtime.state.value}")
        print(f"Input: {args.text}")

        if args.raw:
            engine = runtime._engine
            if engine is None:
                print("Engine missing after ready state.")
                return 1

            messages = engine._format_prompt(
                args.text,
                profile=args.level,
                user_instructions=args.instructions,
                use_thinking=args.thinking,
            )

            t0 = time.perf_counter()
            response = engine.llm.create_chat_completion(
                messages=messages,
                max_tokens=512,
                temperature=max(args.temperature, 0.01),
                top_p=args.top_p,
                top_k=args.top_k,
                stop=["<|im_end|>", "<|endoftext|>"],
            )
            dt = time.perf_counter() - t0

            raw_output = response["choices"][0]["message"]["content"]
            parsed = engine._parse_output(raw_output)

            print(f"Elapsed: {dt:.2f}s")
            print("--- RAW OUTPUT ---")
            print(raw_output)
            print("--- PARSED OUTPUT ---")
            print(parsed.content)
            print(f"Reasoning present: {bool(parsed.reasoning)}")
            print(f"Changed: {parsed.content.strip() != args.text.strip()}")
            return 0

        engine = runtime._engine
        if engine is None:
            print("Engine missing after ready state.")
            return 1

        t0 = time.perf_counter()
        result = engine.refine(
            args.text,
            profile=args.level,
            user_instructions=args.instructions,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            use_thinking=args.thinking,
        )
        dt = time.perf_counter() - t0

        print(f"Elapsed: {dt:.2f}s")
        print(f"Output: {result.content}")
        print(f"Reasoning present: {bool(result.reasoning)}")
        print(f"Changed: {result.content.strip() != args.text.strip()}")
        return 0
    finally:
        runtime.disable()


if __name__ == "__main__":
    raise SystemExit(main())
