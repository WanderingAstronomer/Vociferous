"""
Replay Protection Logic for IPC.

Ensures that messages are processed exactly once within a validity window.
Prevents Replay Attacks and Accidental Duplication.
"""

import time
import threading
import logging
from enum import Enum, auto
from typing import Dict
from uuid import UUID


logger = logging.getLogger(__name__)


class ReplayDecision(Enum):
    ACCEPTED = auto()
    DUPLICATE = auto()
    EXPIRED = auto()
    FUTURE_TIMESTAMP = auto()


class ReplayGuard:
    """
    Tracks recent message IDs used within a validity window.
    Thread-safe.
    """

    def __init__(
        self,
        window_seconds: float = 30.0,
        future_tolerance: float = 5.0,
        cleanup_interval: float = 60.0,
    ):
        """
        Args:
            window_seconds: Max age of a message before it's considered expired.
            future_tolerance: Max seconds a timestamp can be in the future (skew).
            cleanup_interval: How often to purge old IDs from memory.
        """
        self.window = window_seconds
        self.tolerance = future_tolerance
        self.cleanup_interval = cleanup_interval

        self._seen_ids: Dict[UUID, float] = {}
        self._last_cleanup = time.time()
        self._lock = threading.Lock()

    def validate(self, msg_id: UUID, timestamp: float) -> ReplayDecision:
        """
        Check if a message is valid for processing.
        Updates internal state if accepted.
        """
        now = time.time()

        with self._lock:
            # 1. Check Hygiene (Garbage Collection)
            if now - self._last_cleanup > self.cleanup_interval:
                self._prune_expired(now)
                self._last_cleanup = now

            # 2. Check Duplication
            if msg_id in self._seen_ids:
                logger.warning(f"Replay detected: {msg_id}")
                return ReplayDecision.DUPLICATE

            # 3. Check Window (Expired)
            # Message must be newer than (now - window)
            if timestamp < (now - self.window):
                logger.warning(
                    f"Message expired: {msg_id} (Ts: {timestamp}, Cutoff: {now - self.window})"
                )
                return ReplayDecision.EXPIRED

            # 4. Check Future (Clock Skew)
            if timestamp > (now + self.tolerance):
                logger.warning(
                    f"Future timestamp: {msg_id} (Ts: {timestamp}, Now: {now})"
                )
                return ReplayDecision.FUTURE_TIMESTAMP

            # 5. Accept
            self._seen_ids[msg_id] = timestamp
            return ReplayDecision.ACCEPTED

    def cleanup(self) -> None:
        """Force a cleanup of expired IDs."""
        with self._lock:
            self._prune_expired(time.time())

    def _prune_expired(self, now: float) -> None:
        """Internal method to remove old IDs."""
        cutoff = now - self.window
        # Create list to avoid runtime error during iteration
        expired = [mid for mid, ts in self._seen_ids.items() if ts < cutoff]
        for mid in expired:
            del self._seen_ids[mid]

        if expired:
            logger.debug(f"Pruned {len(expired)} expired message IDs.")
