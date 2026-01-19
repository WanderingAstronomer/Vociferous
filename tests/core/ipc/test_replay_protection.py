import time
import pytest
import uuid
from dataclasses import dataclass
from src.core.ipc.structures import MessageHeader, MessageType, HandlerMetadata
from src.core.ipc.replay_guard import ReplayGuard, ReplayDecision


class TestReplayGuard:
    @pytest.fixture
    def guard(self):
        # Window of 5 seconds for testing
        return ReplayGuard(window_seconds=5.0, cleanup_interval=1.0)

    def test_accepts_new_message(self, guard):
        msg_id = uuid.uuid4()
        now = time.time()

        decision = guard.validate(msg_id, now)
        assert decision == ReplayDecision.ACCEPTED

    def test_rejects_duplicate_message(self, guard):
        msg_id = uuid.uuid4()
        now = time.time()

        # First time
        assert guard.validate(msg_id, now) == ReplayDecision.ACCEPTED

        # Second time (immediate replay)
        assert guard.validate(msg_id, now) == ReplayDecision.DUPLICATE

    def test_rejects_expired_message(self, guard):
        msg_id = uuid.uuid4()
        # 10 seconds ago (window is 5)
        past_time = time.time() - 10.0

        decision = guard.validate(msg_id, past_time)
        assert decision == ReplayDecision.EXPIRED

    def test_rejects_future_message(self, guard):
        msg_id = uuid.uuid4()
        # 10 seconds in future (allowance usually small, e.g. 1s)
        future_time = time.time() + 10.0

        decision = guard.validate(msg_id, future_time)
        assert decision == ReplayDecision.FUTURE_TIMESTAMP

    def test_cleanup_purges_old_entries(self, guard):
        old_id = uuid.uuid4()
        uuid.uuid4()
        now = time.time()

        # Inject an old entry manually or simulate time passing
        # Since we mocks time.time() usually, strictly we should use unit test style
        # But for simple integration style:

        # We can simulate internal state for this test if we don't want to sleep
        guard._seen_ids[old_id] = now - 10.0

        guard.cleanup()

        # Old ID should be gone (so if it comes again with NEW timestamp? No, ID is unique)
        # If we send old_id again with CURRENT timestamp?
        # ReplayGuard checks ID first.

        assert old_id not in guard._seen_ids

    def test_respects_idempotency_metadata(self, guard):
        """
        If a message is marked idempotent, the ReplayGuard *might* still block it
        if we strictly enforcing 'once'.
        However, if the requirement implies handling idempotence, maybe we allow it?

        Let's assume ReplayGuard simply logs or returns a specific decision type for duplicates
        that allows the caller to override if idempotent.
        """
        msg_id = uuid.uuid4()
        now = time.time()

        guard.validate(msg_id, now)
        decision = guard.validate(msg_id, now)

        assert decision == ReplayDecision.DUPLICATE
        # The caller (Dispatcher) decides whether to ignore DUPLICATE if intent.is_idempotent

    def test_handler_metadata_structure(self):
        """Verify HandlerMetadata can be instantiated and holds flags."""
        meta = HandlerMetadata(
            handler_id="test_handler",
            supported_types={MessageType.COMMAND},
            is_idempotent=True,
            priority=10,
        )

        assert meta.is_idempotent is True
        assert meta.requires_ack is True  # Default
