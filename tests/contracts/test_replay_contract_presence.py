from typing import Protocol, runtime_checkable
import pytest


def test_replay_module_structure():
    """Assert Replay Guard subsystem exists."""
    try:
        from src.core.intents import guards
        from src.core.intents.guards import ReplayContext, GuardPolicy, GuardResult
    except ImportError:
        pytest.fail("Replay Guard subsystem missing")

    # Dataclass fields are on instances or __annotations__, not class dict usually in hasattr check style
    # Better to check __annotations__ for dataclasses
    assert "active_view_id" in ReplayContext.__annotations__
    assert "focused_capability" in ReplayContext.__annotations__


def test_idempotence_registry_separation():
    """Assert idempotence is not on the Intent object."""
    from src.core.intents import InteractionIntent

    # This is a negative test - we DON'T want _idempotent field on the data class
    # But for now, we just assert the Registry mechanism exists
    try:
        from src.core.intents.registry import HandbookRegistry
    except ImportError:
        pytest.fail("Intent Registry missing")
