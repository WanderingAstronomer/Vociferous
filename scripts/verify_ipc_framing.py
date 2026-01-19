import sys
from pathlib import Path
import struct
import io

# Adjust path to import src
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

try:
    from src.core_runtime.protocol.transport import (
        PacketTransport,
        ProtocolMessage,
        MessageType,
        MAGIC,
        HEADER_SIZE,
    )

    print("=== IPC Transport Verification ===")

    # 1. Check Magic
    print(f"Magic Bytes: {MAGIC}")

    # 2. Check Framing Logic (Mock)
    mock_out = io.BytesIO()
    mock_in = io.BytesIO()
    transport = PacketTransport(mock_in, mock_out)

    msg = ProtocolMessage(MessageType.HANDSHAKE, {"ver": "1.0"})
    transport.send_message(msg)

    data = mock_out.getvalue()
    print(f"Serialized Length: {len(data)}")

    # Analyze Header
    header = data[:HEADER_SIZE]
    magic, ftype, length, checksum = struct.unpack(">4sBII", header)
    print(f"Header: Magic={magic}, Type={ftype}, Len={length}, CRC={checksum:x}")

    # Check Checksum
    import zlib

    payload = data[HEADER_SIZE:]
    calc_crc = zlib.crc32(payload) & 0xFFFFFFFF
    print(f"Calculated CRC: {calc_crc:x}")
    print(f"CRC Match: {checksum == calc_crc}")

except ImportError:
    print("Failed to import core_runtime")
