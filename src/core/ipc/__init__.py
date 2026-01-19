"""
Inter-Process Communication Subsystem.

Provides primitives for safe, hardened communication between
process boundaries (e.g. GUI and Engine).
"""

from .structures import (
    HandlerMetadata as HandlerMetadata,
    IPCMessage as IPCMessage,
    MessageHeader as MessageHeader,
    MessageType as MessageType,
)
from .replay_guard import (
    ReplayDecision as ReplayDecision,
    ReplayGuard as ReplayGuard,
)
