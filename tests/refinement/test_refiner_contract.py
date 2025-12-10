"""Refiner contract tests using CLI with rule-based refiner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


@pytest.fixture(autouse=True)
def ensure_artifacts_dir() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "vociferous.cli.main", *args],
        cwd=ARTIFACTS_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture
def raw_transcript() -> Path:
    path = ARTIFACTS_DIR / "test_raw_transcript.txt"
    path.write_text(
        "uh  so like i was thinking   um we should maybe do that thing you know the pro- ject from last week",
        encoding="utf-8",
    )
    return path


def test_refiner_contract(raw_transcript: Path) -> None:
    """Refiner produces polished transcript from raw text via CLI."""
    output_file = ARTIFACTS_DIR / "test_refined_transcript.txt"

    result = _run_cli([
        "refine",
        str(raw_transcript),
        "--output",
        str(output_file),
        "--model",
        "rule",
    ])

    assert result.returncode == 0, f"Refine failed: {result.stderr}"
    assert output_file.exists(), "Refined transcript not created"

    refined_text = output_file.read_text(encoding="utf-8")
    assert refined_text.strip(), "Refined transcript is empty"
    assert refined_text != raw_transcript.read_text(encoding="utf-8"), "Refined text identical to raw"


def test_refiner_handles_empty_input() -> None:
    """Refiner exits with error on empty transcript."""
    empty_file = ARTIFACTS_DIR / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    result = _run_cli([
        "refine",
        str(empty_file),
        "--model",
        "rule",
    ])

    assert result.returncode != 0
    assert "empty" in result.stderr.lower()


def test_refiner_custom_instructions(raw_transcript: Path) -> None:
    """Refiner accepts custom instructions and succeeds."""
    output_file = ARTIFACTS_DIR / "test_refined_custom.txt"

    result = _run_cli([
        "refine",
        str(raw_transcript),
        "--output",
        str(output_file),
        "--model",
        "rule",
        "--instructions",
        "Make text concise",
    ])

    assert result.returncode == 0, f"Refine failed: {result.stderr}"
    assert output_file.exists()
    refined_text = output_file.read_text(encoding="utf-8")
    assert refined_text.strip()
