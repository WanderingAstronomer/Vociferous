"""Test AudioChunk domain type."""
import pytest

from vociferous.domain.model import AudioChunk


def test_audio_chunk_creation() -> None:
    """Test creating an AudioChunk with all fields."""
    chunk = AudioChunk(
        samples=b"\x00\x01\x02\x03",
        sample_rate=16000,
        channels=1,
        start_s=0.0,
        end_s=1.0,
    )
    assert chunk.samples == b"\x00\x01\x02\x03"
    assert chunk.sample_rate == 16000
    assert chunk.channels == 1
    assert chunk.start_s == 0.0
    assert chunk.end_s == 1.0


def test_audio_chunk_stereo() -> None:
    """Test creating AudioChunk with stereo (2 channels)."""
    chunk = AudioChunk(
        samples=b"\x00\x01\x02\x03",
        sample_rate=44100,
        channels=2,
        start_s=0.0,
        end_s=0.5,
    )
    assert chunk.channels == 2
    assert chunk.sample_rate == 44100


def test_audio_chunk_immutable() -> None:
    """Test AudioChunk is frozen (immutable)."""
    chunk = AudioChunk(
        samples=b"test",
        sample_rate=16000,
        channels=1,
        start_s=0.0,
        end_s=1.0,
    )
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        chunk.sample_rate = 8000  # type: ignore[misc]


def test_audio_chunk_empty_samples() -> None:
    """Test AudioChunk can have empty samples."""
    chunk = AudioChunk(
        samples=b"",
        sample_rate=16000,
        channels=1,
        start_s=0.0,
        end_s=0.0,
    )
    assert chunk.samples == b""
    assert len(chunk.samples) == 0


def test_audio_chunk_time_range() -> None:
    """Test AudioChunk time range properties."""
    chunk = AudioChunk(
        samples=b"test",
        sample_rate=16000,
        channels=1,
        start_s=2.5,
        end_s=5.0,
    )
    assert chunk.start_s == 2.5
    assert chunk.end_s == 5.0
    duration = chunk.end_s - chunk.start_s
    assert duration == 2.5
