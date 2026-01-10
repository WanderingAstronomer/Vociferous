"""
Test single-instance enforcement.
"""

import os
import subprocess
import time


def test_single_instance_enforcement():
    """Test that only one instance of Vociferous can run at a time."""
    from pathlib import Path

    # Path to run script
    run_script = Path(__file__).parent.parent / "scripts" / "run.py"
    python = Path(__file__).parent.parent / ".venv" / "bin" / "python"

    # Start first instance
    proc1 = subprocess.Popen(
        [str(python), str(run_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )

    # Give it time to acquire lock
    time.sleep(1)

    # Try to start second instance (should fail immediately)
    proc2 = subprocess.Popen(
        [str(python), str(run_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ.copy(),
    )

    # Wait for second instance to exit
    try:
        proc2.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc2.kill()
        proc2.wait()
        assert False, "Second instance did not exit (lock not working)"

    # Second instance should have exited with code 1
    assert proc2.returncode == 1, f"Expected exit code 1, got {proc2.returncode}"

    # Clean up first instance
    proc1.terminate()
    try:
        proc1.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc1.kill()
        proc1.wait()
