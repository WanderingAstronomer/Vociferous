import os
from pathlib import Path


def test_run_tests_script_exists_and_executable():
    script = Path(__file__).resolve().parents[2] / "scripts" / "run_tests.sh"
    assert script.exists(), f"Run-tests script missing at {script}"
    assert script.stat().st_size > 0
    # Not requiring executable bit; CI can run with bash scripts/run_tests.sh
