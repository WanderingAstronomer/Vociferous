import pytest
from unittest.mock import MagicMock

from src.database.repositories.transcript_repo import TranscriptRepository
from src.core.exceptions import DatabaseError


class _FakeSessionCM:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        pass

    def commit(self):
        raise Exception("Simulated commit failure")


def test_add_entry_raises_on_commit_error():
    db_core = MagicMock()
    db_core.get_session.return_value = _FakeSessionCM()

    repo = TranscriptRepository(db_core)

    with pytest.raises(DatabaseError):
        repo.add_entry("Test text", duration_ms=100, speech_duration_ms=50)
