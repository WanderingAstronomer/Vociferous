"""
Integration test for IPC. Spawns real server process.
"""

import time
import pytest
import threading
from queue import Queue

from src.core_runtime.client import EngineClient
from src.core_runtime.types import TranscriptionResult, EngineState


@pytest.mark.integration
def test_client_server_handshake():
    result_queue = Queue()

    def on_result(res):
        result_queue.put(res)

    client = EngineClient(on_result=on_result)

    try:
        # 1. Connect (Spawns process)
        client.connect()

        # Give it a moment to stabilize/handshake
        time.sleep(1)

        assert client.process.poll() is None, "Server process died unexpectedly"

        # 2. Trigger Session (might fail if no mic, but we check if command sends)
        # Note: server will try to init audio. If no mic, it might error.
        # But we just want to ensure IPC works.
        client.start_session()

        # 3. Stop
        client.stop_session()

    finally:
        client.shutdown()

    # Check that process is gone
    assert client.process is None
