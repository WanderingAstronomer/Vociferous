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

    # Path to entry point script
    from tests.conftest import PROJECT_ROOT

    project_root = PROJECT_ROOT
    # Target src/main.py directly to test the lock logic without wrapper complexity
    run_script = project_root / "src" / "main.py"

    python_exe = sys.executable

    # Define custom lock path for test isolation
    test_lock_path = tmp_path / "vociferous_test.lock"

    # Environment with adjusted generic config to avoid interfering with real config
    env = os.environ.copy()
    env["VOCIFEROUS_LOCK_PATH"] = str(test_lock_path)
    env["PYTHONPATH"] = str(project_root)  # Ensure src module resolution
    # Assuming standard XDG, force it to tmp_path
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")

    # Create config dir
    (tmp_path / "config").mkdir()

    # Force offscreen platform to avoid X11/Wayland connection issues during test
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["XDG_RUNTIME_DIR"] = str(
        tmp_path / "runtime"
    )  # Avoid real runtime dir conflicts
    (tmp_path / "runtime").mkdir()

    # Launch Instance 1
    proc1 = subprocess.Popen(
        [python_exe, str(run_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )

    try:
        # Invariant: First instance acquires lock.
        start_time = time.time()
        lock_acquired = False

        while time.time() - start_time < 10:
            if proc1.poll() is not None:
                stdout, stderr = proc1.communicate()
                print(f"CRASH: Instance 1 exited with code {proc1.returncode}")
                print(f"STDOUT: {stdout}")
                print(f"STDERR: {stderr}")
                pytest.fail(
                    f"Instance 1 crashed unexpectedly.\nSTDOUT: {stdout}\nSTDERR: {stderr}"
                )

            if test_lock_path.exists():
                lock_acquired = True
                break
            time.sleep(0.5)

        if not lock_acquired:
            # Debugging: Why didn't it acquire?
            if proc1.poll() is None:
                proc1.terminate()
                try:
                    stdout, stderr = proc1.communicate(timeout=2)
                    pytest.fail(
                        f"TIMEOUT: Instance 1 running but no lock.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
                    )
                except subprocess.TimeoutExpired:
                    proc1.kill()
                    pytest.fail("TIMEOUT: Instance 1 hung and refused terminate.")

        assert lock_acquired, "Instance 1 failed to acquire lock file within 10s"

        # Launch Instance 2
        proc2 = subprocess.Popen(
            [python_exe, str(run_script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )

        try:
            # Invariant: Second instance checks lock, prints message, and exits.
            stdout_2, stderr_2 = proc2.communicate(timeout=15)

            assert "already running" in stderr_2 or "already running" in stdout_2

        except subprocess.TimeoutExpired as e:
            proc2.kill()
            out = e.stdout.decode() if e.stdout else ""
            err = e.stderr.decode() if e.stderr else ""
            print(f"Proc2 STDOUT: {out}")
            print(f"Proc2 STDERR: {err}")
            pytest.fail(
                f"Second instance hung (did not respect single-instance lock).\nStdout: {out}\nStderr: {err}"
            )

    finally:
        # Cleanup Instance 1
        if proc1.poll() is None:
            proc1.terminate()
            with suppress(subprocess.TimeoutExpired):
                proc1.wait(timeout=2)
            if proc1.poll() is None:
                proc1.kill()
