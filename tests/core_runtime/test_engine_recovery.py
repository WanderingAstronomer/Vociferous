import sys
import time
import pytest
import threading
from src.core_runtime.client import EngineClient
from src.core_runtime.types import EngineState, TranscriptionResult


class RecoveryTestState:
    def __init__(self):
        self.states = []
        self.error_received = threading.Event()
        self.ready_received = threading.Event()

    def on_result(self, res: TranscriptionResult):
        self.states.append(res.state)
        if res.state == EngineState.ERROR:
            self.error_received.set()
        # We don't have explicit READY state in TranscriptionResult enum (it has IDLE/RECORDING/etc)
        # But we can infer ready from Handshake ACK logs or successful subsequent start_session?

    def on_status(self, status: str):
        if status == "ready":
            self.ready_received.set()


def test_engine_crash_recovery():
    """
    Integration Test:
    1. Start Engine
    2. Wait for connectivity
    3. Kill Engine Process
    4. Assert Client detects loss (Error)
    5. Restart Engine
    6. Assert Connectivity restored
    """

    state_tracker = RecoveryTestState()

    # 1. Start
    client = EngineClient(
        on_result=state_tracker.on_result, on_status=state_tracker.on_status
    )
    client.connect()

    # Wait for startup (simple sleep or status callback)
    # The current server sends HANDSHAKE_ACK but Client just logs it.
    # Client doesn't expose 'on_ready'.
    # We'll assume connected if process is alive.
    time.sleep(2)
    assert client.process.poll() is None

    # 2. Kill
    print("Killing Engine...")
    client.process.terminate()
    client.process.wait()

    # 3. Assert Detection
    # Watchdog or Listener should trigger.
    # We wait up to Heartbeat Timeout (5s) + buffer.
    # Since we killed it, Listener (EOF) should be fast.
    if not state_tracker.error_received.wait(timeout=5.0):
        pytest.fail("Client did not report ERROR after process death")

    assert EngineState.ERROR in state_tracker.states

    # 4. Restart
    print("Restarting Engine...")
    client.shutdown()  # Clean up old threads
    client.connect()

    time.sleep(2)
    assert client.process.poll() is None

    # 5. Verify Liveness
    # Send START_SESSION, should not crash
    try:
        client.start_session()
        time.sleep(1)
        client.stop_session()
    except Exception as e:
        pytest.fail(f"Failed to use restarted engine: {e}")

    client.shutdown()
