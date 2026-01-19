"""
IPC Core Types and Structures.

Defines the primitives for Inter-Process Communication, including
Headers, Message Types, and Handler Metadata.
"""

from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, Dict, Any
import uuid


class MessageType(IntEnum):
    """
    Categorization of IPC messages for routing and priority.
    """

    HEARTBEAT = 0x01
    COMMAND = 0x10  # Direct imperative (Do X)
    EVENT = 0x20  # Notification (X happened)
    QUERY = 0x30  # Data request (Get X)
    RESPONSE = 0x31  # Data reply
    ERROR = 0xFF


@dataclass(frozen=True, slots=True)
class MessageHeader:
    """
    Standard framing header for IPC Messages.
    Format: Magic(4s) | Type(B) | Flags(B) | Len(I) | CRC(I)
    """

    msg_type: MessageType
    payload_length: int
    msg_id: uuid.UUID
    timestamp: float  # Unix timestamp
    flags: int = 0

    # Flags constants
    FLAG_ENCRYPTED = 0x01
    FLAG_COMPRESSED = 0x02
    FLAG_PRIORITY = 0x04


@dataclass(frozen=True, slots=True)
class HandlerMetadata:
    """
    Capabilities and constraints for an IPC Handler.
    Used for routing and validation.
    """

    handler_id: str
    supported_types: set[MessageType]
    is_idempotent: bool = False
    requires_ack: bool = True
    priority: int = 0


@dataclass(frozen=True, slots=True)
class IPCMessage:
    """
    Full envelope for an IPC transmission.
    """

    header: MessageHeader
    payload: bytes
    metadata: Optional[Dict[str, Any]] = None
