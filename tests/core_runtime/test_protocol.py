"""
Tests for the Protocol and Transport layer.
"""

import io
import threading
import json
import pytest
from src.core_runtime.protocol.types import ProtocolMessage, MessageType
from src.core_runtime.protocol.transport import PacketTransport, TransportError


def test_json_message_roundtrip():
    """Verify JSON messages can be sent and received."""
    # Create pipe-like buffers (but need to manage read/write cursors)
    # Using io.BytesIO needs care because write moves cursor.
    # Better to use a real pipe or just manage buffer position.

    # Simpler: Write to one buffer, read from it.
    buffer = io.BytesIO()

    transport_write = PacketTransport(io.BytesIO(), buffer)  # Reader is dummy

    msg = ProtocolMessage(msg_type=MessageType.HANDSHAKE, payload={"version": "1.0"})

    transport_write.send_message(msg)

    # Reset cursor to read
    buffer.seek(0)

    transport_read = PacketTransport(buffer, io.BytesIO())  # Writer is dummy
    received = transport_read.receive()

    assert isinstance(received, ProtocolMessage)
    assert received.msg_type == MessageType.HANDSHAKE
    assert received.payload["version"] == "1.0"


def test_audio_frame_roundtrip():
    """Verify Audio chunks can be sent and received."""
    buffer = io.BytesIO()
    transport_write = PacketTransport(io.BytesIO(), buffer)

    audio_data = b"\x00\x01\x02\x03" * 10
    transport_write.send_audio(audio_data)

    buffer.seek(0)
    transport_read = PacketTransport(buffer, io.BytesIO())

    received = transport_read.receive()
    assert isinstance(received, bytes)
    assert received == audio_data


def test_interleaved_messages():
    """Verify mixed JSON and Audio."""
    buffer = io.BytesIO()
    transport_write = PacketTransport(io.BytesIO(), buffer)

    msg1 = ProtocolMessage(MessageType.START_SESSION)
    audio = b"beep"
    msg2 = ProtocolMessage(MessageType.STOP_SESSION)

    transport_write.send_message(msg1)
    transport_write.send_audio(audio)
    transport_write.send_message(msg2)

    buffer.seek(0)
    transport_read = PacketTransport(buffer, io.BytesIO())

    r1 = transport_read.receive()
    r2 = transport_read.receive()
    r3 = transport_read.receive()

    assert isinstance(r1, ProtocolMessage) and r1.msg_type == MessageType.START_SESSION
    assert r2 == audio
    assert isinstance(r3, ProtocolMessage) and r3.msg_type == MessageType.STOP_SESSION


def test_incomplete_read_returns_none():
    """Verify handling of closed stream."""
    buffer = io.BytesIO(b"PartialGarbage")
    transport = PacketTransport(buffer, io.BytesIO())

    # Should probably raise error or return None depending on impl
    # Our impl:
    # read(HEADER) -> if partial -> Error

    with pytest.raises(TransportError):
        transport.receive()
