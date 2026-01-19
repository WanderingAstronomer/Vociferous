#!/usr/bin/env python3
"""
Manual Test Script for Refinement Engine Semantics.
Tests different refinement profiles and custom prompts against varied inputs.
"""

import sys
import logging
from pathlib import Path
import time

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.core.config_manager import ConfigManager, get_model_cache_dir  # noqa: E402
from src.refinement.engine import RefinementEngine  # noqa: E402
from src.core.model_registry import MODELS  # noqa: E402

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ManualTest")


def main():
    logger.info("Initializing ConfigManager...")
    # Initialize config (assumes running from root or scripts, handling path resolution)
    ConfigManager.initialize(project_root / "src" / "config_schema.yaml")

    # Load Model Info
    model_id = ConfigManager.get_config_value("refinement", "model_id") or "qwen4b"
    model_info = MODELS.get(model_id)
    if not model_info:
        logger.error(f"Unknown model ID: {model_id}")
        return

    cache_dir = get_model_cache_dir()
    model_dir = cache_dir / model_info.dir_name
    tokenizer_path = model_dir / "tokenizer.json"

    if not model_dir.exists():
        logger.error(
            f"Model not found at {model_dir}. Please run the app to provision it."
        )
        return

    # Load Prompts from Config
    sys_prompt = ConfigManager.get_config_value("prompts", "refinement_system")
    invariants = ConfigManager.get_config_value("prompts", "refinement_invariants")
    levels = ConfigManager.get_config_value("prompts", "refinement_levels")

    logger.info("Loading Refinement Engine (this takes a few seconds)...")
    try:
        engine = RefinementEngine(
            model_path=model_dir,
            tokenizer_path=tokenizer_path,
            system_prompt=sys_prompt,
            invariants=invariants,
            levels=levels,
            device="auto",  # Will auto-select CUDA if available/configured
        )
    except Exception as e:
        logger.error(f"Failed to load engine: {e}")
        return

    # Test Cases
    test_cases = [
        {
            "name": "Minimal Refinement (Typos & Formatting)",
            "input": "hello this is a test. i am writinge with some typos and no caps.",
            "profile": "MINIMAL",
            "expected_behavior": "Should fix caps/spelling, keep simple structure.",
        },
        {
            "name": "Minimal Refinement (Filler Preservation)",
            "input": "So, um, basically, I think that, uh, we should go.",
            "profile": "MINIMAL",
            "expected_behavior": "Should keep 'um' and 'uh' mostly intact per 'Do not remove filler words'.",
        },
        {
            "name": "Balanced Refinement (Stutter Removal)",
            "input": "I I I want to go to the the the store.",
            "profile": "BALANCED",
            "expected_behavior": "Should remove repeated words.",
        },
        {
            "name": "Strong Refinement (Flow & Smoothing)",
            "input": "It was raining really hard and the car broke down and we were stuck there for hours and it was cold.",
            "profile": "STRONG",
            "expected_behavior": "Should split sentences or smooth the flow.",
        },
        {
            "name": "Custom Instruction (Transform)",
            "input": "The quick brown fox jumps over the lazy dog.",
            "profile": "BALANCED",  # Profile still applies base rules
            "instructions": "Replace animal names with 'unknown entity'.",
            "expected_behavior": "Should replace fox/dog with 'unknown entity'.",
        },
        {
            "name": "Long Content Test",
            "input": (
                "so yesterday i went to the park and i saw a bird it was blue and "
                "i took a picture but it flew away before i could get a good shot so "
                "i was sad but then i got ice cream and it was okay."
            ),
            "profile": "STRONG",
            "expected_behavior": "Should handle longer context and punctuate properly.",
        },
        {
            "name": "Overkill Refinement (Rewriting/Boosting)",
            "input": "i went to the store to get food cause i was hungry and it was good.",
            "profile": "OVERKILL",
            "expected_behavior": "Should rewrite with better vocal, e.g. 'I visited the market to purchase sustenance...'",
        },
    ]

    print("\n" + "=" * 60)
    print(" STARTING MANUAL COMPREHENSIVE TEST")
    print("=" * 60 + "\n")

    for case in test_cases:
        name = case["name"]
        inp = case["input"]
        prof = case["profile"]
        inst = case.get("instructions", "")
        exp = case["expected_behavior"]

        print(f"--- TEST CASE: {name} ---")
        print(f"Profile: {prof}")
        if inst:
            print(f"Instructions: {inst}")
        print(f"Input:    {inp}")

        start = time.perf_counter()
        result = engine.refine(
            text=inp,
            profile=prof,
            user_instructions=inst,
            temperature=0.0,  # Deterministic
        )
        dur = time.perf_counter() - start

        print(f"Output:   {result.content}")
        if result.reasoning:
            print(f"Thinking: {result.reasoning[:100]}...")
        print(f"Time:     {dur:.2f}s")
        print(f"Expect:   {exp}")
        print("-" * 40 + "\n")


if __name__ == "__main__":
    main()
