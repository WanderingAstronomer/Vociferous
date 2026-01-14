"""
Test single-instance enforcement.
"""

import os
import sys
import subprocess
import time
import pytest
from pathlib import Path
from contextlib import suppress

# Mark as system-dependent/integration to avoid flakiness in unit suites
pytestmark = pytest.mark.integration

def test_single_instance_enforcement(tmp_path):
    """
    Invariant: Only one instance of Vociferous can run at a time.
    Second instance must detect lock and exit gracefully.
    """
    
    # Path to run script
    project_root = Path(__file__).resolve().parent.parent
    run_script = project_root / "scripts" / "run.py"
    
    python_exe = sys.executable

    # Define custom lock path for test isolation
    test_lock_path = tmp_path / "vociferous_test.lock"
    
    # Environment with adjusted generic config to avoid interfering with real config
    env = os.environ.copy()
    env["VOCIFEROUS_LOCK_PATH"] = str(test_lock_path)
    # Assuming standard XDG, force it to tmp_path
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    
    # Create config dir
    (tmp_path / "config").mkdir()

    # Launch Instance 1
    proc1 = subprocess.Popen(
        [python_exe, str(run_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True
    )

    try:
        # Invariant: First instance acquires lock.
        start_time = time.time()
        lock_acquired = False
        
        while time.time() - start_time < 5:
            if proc1.poll() is not None:
                stdout, stderr = proc1.communicate()
                pytest.fail(f"Instance 1 crashed unexpectedly.\nSTDOUT: {stdout}\nSTDERR: {stderr}")
            
            if test_lock_path.exists():
                lock_acquired = True
                break
            time.sleep(0.1)

        assert lock_acquired, "Instance 1 failed to acquire lock file"

        # Launch Instance 2
        proc2 = subprocess.Popen(
            [python_exe, str(run_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )

        try:
            # Invariant: Second instance checks lock, prints message, and exits.
            stdout_2, stderr_2 = proc2.communicate(timeout=5)
            
            assert "already running" in stderr_2 or "already running" in stdout_2
            
        except subprocess.TimeoutExpired:
            proc2.kill()
            pytest.fail("Second instance hung (did not respect single-instance lock)")
            
    finally:
        # Cleanup Instance 1
        if proc1.poll() is None:
            proc1.terminate()
            with suppress(subprocess.TimeoutExpired):
                 proc1.wait(timeout=2)
            if proc1.poll() is None:
                proc1.kill()
