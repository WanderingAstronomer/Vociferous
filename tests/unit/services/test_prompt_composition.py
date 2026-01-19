import sys
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest

# Import the module normally - we will patch attributes
import src.refinement.engine as engine_module


@pytest.fixture
def engine():
    mock_model_path = MagicMock(spec=Path)
    mock_model_path.exists.return_value = True

    mock_tok_path = MagicMock(spec=Path)
    mock_tok_path.exists.return_value = True

    system_prompt = "SYSTEM_PROMPT_CONTENT"
    levels = {
        1: {
            "role": "BALANCED_ROLE",
            "permitted": ["BALANCED_PERMITTED"],
            "prohibited": ["BALANCED_PROHIBITED"],
            "directive": "BALANCED_DIRECTIVE",
        },
        2: {
            "role": "STRONG_ROLE",
            "permitted": ["STRONG_PERMITTED"],
            "prohibited": ["STRONG_PROHIBITED"],
            "directive": "STRONG_DIRECTIVE",
        },
    }

    # Patch dependencies directly on the imported module
    # This works regardless of whether global import mocks happened earlier
    with (
        patch.object(engine_module, "ctranslate2", MagicMock()),
        patch.object(engine_module, "Tokenizer", MagicMock()),
    ):
        return engine_module.RefinementEngine(
            model_path=mock_model_path,
            tokenizer_path=mock_tok_path,
            system_prompt=system_prompt,
            levels=levels,
            device="cpu",
        )


def test_prompt_includes_system_prompt(engine):
    """Verify system prompt is correctly injected into ChatML format."""
    prompt = engine._format_prompt("User Text", "BALANCED")

    assert "SYSTEM_PROMPT_CONTENT" in prompt
    assert "<|im_start|>system" in prompt


def test_prompt_includes_profile_rule(engine):
    """Verify correct profile rule is selected."""
    # Balanced
    prompt = engine._format_prompt("Input", "BALANCED")
    assert "BALANCED_ROLE" in prompt
    assert "BALANCED_PERMITTED" in prompt
    assert "STRONG_ROLE" not in prompt

    # Strong
    prompt_strong = engine._format_prompt("Input", "STRONG")
    assert "STRONG_ROLE" in prompt_strong


def test_prompt_includes_user_instructions(engine):
    """Verify user instructions are appended to directives."""
    instructions = "Make it sound like Shakespeare."
    prompt = engine._format_prompt(
        "Original Text", "BALANCED", user_instructions=instructions
    )

    # Note: "User Instructions" also appears in few-shot examples if has_instructions is True
    assert "User Instructions: Make it sound like Shakespeare." in prompt

    # Check that the specific instruction appears AFTER the actual task start
    assert prompt.find(
        "User Instructions: Make it sound like Shakespeare."
    ) > prompt.find("--- ACTUAL TASK ---")


def test_user_instructions_empty_behavior(engine):
    """Verify no phantom instruction header when empty."""
    prompt = engine._format_prompt("Original Text", "BALANCED", user_instructions="   ")
    # In this case, "User Instructions" should not appear at all because has_instructions=False
    # so even few-shot examples won't have it.
    assert "User Instructions" not in prompt


def test_prompt_structure_invariants(engine):
    """Verify critical structural markers are present."""
    prompt = engine._format_prompt("Some transcript text", "BALANCED")

    assert "<<<BEGIN TRANSCRIPT>>>" in prompt
    assert "Some transcript text" in prompt
    assert "<<<END TRANSCRIPT>>>" in prompt

    # Check ChatML structure
    assert "<|im_start|>system" in prompt
    assert "<|im_start|>user" in prompt
    assert "<|im_start|>assistant" in prompt
