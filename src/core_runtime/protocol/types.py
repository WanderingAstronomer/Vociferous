"""
Protocol Message Definitions.

Defines the data structures for communication between the UI (Client) and
the Headless Engine (Server).

Serialization: JSON for Control, Binary for Audio (handled by Transport).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class MessageType(str, Enum):
    # Lifecycle
    HANDSHAKE = "handshake"
    HANDSHAKE_ACK = "handshake_ack"
    SHUTDOWN = "shutdown"
    HEARTBEAT = "heartbeat"

    # Command (UI -> Engine)
    START_SESSION = "start_session"
    STOP_SESSION = "stop_session"
    UPDATE_CONFIG = "update_config"

    # Data (Engine -> UI)
    TRANSCRIPT_UPDATE = "transcript_update"
    AUDIO_LEVEL = "audio_level"
    AUDIO_SPECTRUM = "audio_spectrum"
    STATUS_UPDATE = "status_update"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ProtocolMessage:
    """Base class for all protocol messages."""

    msg_type: MessageType
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HandshakePayload:
    protocol_version: str = "1.0"
    client_id: str = "vociferous_ui"


@dataclass(frozen=True, slots=True)
class AudioFrame:
    """
    Representation of an audio chunk.
    NOTE: Audio is typically sent as raw binary frames in the transport layer,
    not serialized as JSON messages, to avoid overhead.
    This class exists for internal handling if needed.
    """

    data: bytes
    sample_rate: int
    channels: int
