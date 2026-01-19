"""
Unit tests for the EngineServer logic.
"""

import threading
import time
import io
import json
from unittest.mock import MagicMock, patch

from src.core_runtime.server import EngineServer
from src.core_runtime.protocol.transport import (
    PacketTransport,
    TYPE_JSON,
    HEADER_STRUCT,
    MAGIC,
)
from src.core_runtime.protocol.types import MessageType, ProtocolMessage

import zlib


def create_message_frame(msg_type, payload):
    data = json.dumps({"type": msg_type, "payload": payload}).encode("utf-8")
    checksum = zlib.crc32(data) & 0xFFFFFFFF
    header = HEADER_STRUCT.pack(MAGIC, TYPE_JSON, len(data), checksum)
    return header + data


def test_handshake_flow():
    # Setup Input Stream (Client -> Server)
    input_buffer = io.BytesIO()
    input_buffer.write(create_message_frame(MessageType.HANDSHAKE, {}))
    input_buffer.write(create_message_frame(MessageType.SHUTDOWN, {}))  # Stop the loop
    input_buffer.seek(0)

    # Setup Output Stream (Server -> Client)
    output_buffer = io.BytesIO()
    output_buffer.close = MagicMock()  # Prevent server from effectively closing it

    # Run Server
    # We patch _preload_model_worker to prevent background loading
    with patch("src.core_runtime.server.EngineServer._preload_model_worker"):
        server = EngineServer(input_buffer, output_buffer)
        server.start()

    # Verify Output
    output_buffer.seek(0)
    transport = PacketTransport(output_buffer, io.BytesIO())  # Only reading

    # Read loop to skip heartbeats
    response = None
    start_time = time.time()
    while time.time() - start_time < 2.0:
        try:
            msg = transport.receive()
            if not msg:
                break

            if isinstance(msg, ProtocolMessage):
                if msg.msg_type == MessageType.HANDSHAKE_ACK:
                    response = msg
                    break
                # Ignore Heartbeats
        except Exception:
            break

    assert response is not None, "Did not receive Handshake ACK"
    assert isinstance(response, ProtocolMessage)
    assert response.msg_type == MessageType.HANDSHAKE_ACK
    assert response.payload["status"] == "ready"


def test_start_session_triggers_engine():
    input_buffer = io.BytesIO()
    input_buffer.write(create_message_frame(MessageType.START_SESSION, {}))
    # input_buffer.write(create_message_frame(MessageType.STOP_SESSION, {})) # Stop recording
    input_buffer.write(create_message_frame(MessageType.SHUTDOWN, {}))  # Stop loop

    input_buffer.seek(0)
    output_buffer = io.BytesIO()

    with (
        patch("src.core_runtime.server.EngineServer._preload_model_worker"),
        patch("src.core_runtime.server.TranscriptionEngine") as mock_engine_class,
        patch("src.services.transcription_service.create_local_model"),
    ):
        mock_engine_instance = mock_engine_class.return_value

        server = EngineServer(input_buffer, output_buffer)
        server.local_model = MagicMock()  # Pre-loaded
        server.start()

        # Verify Engine was instantiated
        assert mock_engine_class.call_count == 1

        # Verify run_pipeline was called (eventually, it runs in thread)
        # We need to wait a sec for thread
        time.sleep(0.1)
        mock_engine_instance.run_pipeline.assert_called()
