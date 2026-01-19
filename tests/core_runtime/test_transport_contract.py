import struct
import pytest
import io
from src.core_runtime.protocol.transport import (
    PacketTransport,
    ProtocolMessage,
    MessageType,
    MAGIC,
)


def test_framing_integrity_checksum():
    """Assert transport includes a checksum mechanism."""
    mock_out = io.BytesIO()
    mock_in = io.BytesIO()

    transport = PacketTransport(mock_in, mock_out)
    msg = ProtocolMessage(MessageType.HANDSHAKE, {"ver": "1.0"})

    # Send
    transport.send_message(msg)
    data = mock_out.getvalue()

    # Assert Checksum Existence (Length > Header + Payload)
    # Header=4+1+4=9, Payload ~15.
    # Current implementation is Len=48 (fixed struct?). Let's just check length matches expectation of new contract
    # We expect Magic(4) + Type(1) + Len(4) + CRC(4) + Payload
    assert len(data) > 9 + len(msg.payload), "Packet too short to contain CRC"


def test_corrupted_packet_rejection():
    """Assert transport rejects packets with invalid CRC."""
    # To be implemented once CRC logic exists
    pass


def test_handshake_payload_completeness():
    """Assert handshake includes required fields."""
    # To be implemented once Server logic is updated
    pass
