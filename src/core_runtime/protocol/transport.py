"""
IPC Transport Layer.

Handles framing, serialization, and stream management for the
Vociferous Engine Protocol.

Frame Format:
[MAGIC (4 bytes)] [TYPE (1 byte)] [LENGTH (4 bytes)] [PAYLOAD (N bytes)]

Magic: b'VOCI'
Types:
  0x01: JSON Control Message
  0x02: Binary Audio Data
"""

import struct
import json
import logging
import threading
import zlib
from typing import BinaryIO, Optional, Union
from src.core_runtime.protocol.types import ProtocolMessage, MessageType

logger = logging.getLogger(__name__)

MAGIC = b"VOCI"
# Handshake is Type 0x00? No, usually Control (0x01). Let's keep existing types.
TYPE_JSON = 0x01
TYPE_AUDIO = 0x02

# New Framing: MAGIC (4), TYPE (1), LENGTH (4), CRC32 (4)
HEADER_STRUCT = struct.Struct(">4sBII")
HEADER_SIZE = HEADER_STRUCT.size


class TransportError(Exception):
    """Transport layer communication failure."""

    pass


class PacketTransport:
    """
    Synchronous framing layer over binary streams with Integrity Check (CRC32).
    """

    def __init__(self, reader: BinaryIO, writer: BinaryIO):
        self.reader = reader
        self.writer = writer
        self._write_lock = threading.Lock()
        self._closed = False

    def send_message(self, message: ProtocolMessage) -> None:
        """Send a structured control message."""
        payload_dict = {"type": message.msg_type.value, "payload": message.payload}
        json_bytes = json.dumps(payload_dict).encode("utf-8")
        self._write_frame(TYPE_JSON, json_bytes)

    def send_audio(self, audio_data: bytes) -> None:
        """Send a binary audio chunk."""
        self._write_frame(TYPE_AUDIO, audio_data)

    def _write_frame(self, frame_type: int, data: bytes) -> None:
        """Encapsulate and write data to the stream with Checksum."""
        if self._closed:
            raise TransportError("Transport closed")

        length = len(data)
        # Calculate CRC32 over payload
        checksum = zlib.crc32(data) & 0xFFFFFFFF

        header = HEADER_STRUCT.pack(MAGIC, frame_type, length, checksum)

        try:
            with self._write_lock:
                self.writer.write(header)
                self.writer.write(data)
                self.writer.flush()
        except (BrokenPipeError, OSError) as e:
            self._closed = True
            logger.error(f"Transport Write Failed: {e}")
            raise TransportError(f"Write failed: {e}") from e

    def receive(self) -> Optional[Union[ProtocolMessage, bytes]]:
        """
        Block until a packet is received and validated.
        Returns ProtocolMessage for JSON packets, or bytes for Audio packets.
        Returns None if stream closed.
        """
        if self._closed:
            return None

        try:
            # 1. Read Header
            header_bytes = self.reader.read(HEADER_SIZE)
            if not header_bytes:
                return None  # EOF

            if len(header_bytes) < HEADER_SIZE:
                raise TransportError("Incomplete header received")

            magic, frame_type, length, checksum = HEADER_STRUCT.unpack(header_bytes)

            if magic != MAGIC:
                raise TransportError(f"Invalid Magic: {magic!r}")

            # 2. Read Payload
            payload = self.reader.read(length)
            if len(payload) < length:
                raise TransportError("Incomplete payload received")

            # 3. Verify Integrity
            calculated_crc = zlib.crc32(payload) & 0xFFFFFFFF
            if calculated_crc != checksum:
                logger.error(
                    f"CRC Mismatch! Expected {checksum:x}, Got {calculated_crc:x}"
                )
                raise TransportError("Packet corruption detected (CRC mismatch)")

            # 4. Decode
            if frame_type == TYPE_JSON:
                return self._decode_json(payload)
            elif frame_type == TYPE_AUDIO:
                return payload
            else:
                logger.warning(f"Unknown frame type: {frame_type}")
                return None

        except (ConnectionResetError, BrokenPipeError):
            self._closed = True
            return None
        except Exception as e:
            logger.error(f"Transport Read Error: {e}")
            raise TransportError(f"Read failed: {e}")

    def _decode_json(self, data: bytes) -> ProtocolMessage:
        try:
            obj = json.loads(data.decode("utf-8"))
            return ProtocolMessage(
                msg_type=MessageType(obj["type"]), payload=obj.get("payload", {})
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"JSON Decode Error: {e}")
            raise TransportError("Invalid JSON message")

    def close(self):
        self._closed = True
        try:
            self.writer.close()
            self.reader.close()
        except OSError:
            pass
