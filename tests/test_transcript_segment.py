"""Test TranscriptSegment domain type."""
import pytest

from vociferous.domain.model import TranscriptSegment


def test_transcript_segment_creation() -> None:
    """Test creating a TranscriptSegment with all fields."""
    segment = TranscriptSegment(
        text="Hello world",
        start_s=0.0,
        end_s=1.5,
        language="en",
        confidence=0.95,
    )
    assert segment.text == "Hello world"
    assert segment.start_s == 0.0
    assert segment.end_s == 1.5
    assert segment.language == "en"
    assert segment.confidence == 0.95


def test_transcript_segment_with_different_language() -> None:
    """Test TranscriptSegment with non-English language."""
    segment = TranscriptSegment(
        text="Bonjour le monde",
        start_s=0.0,
        end_s=2.0,
        language="fr",
        confidence=0.88,
    )
    assert segment.language == "fr"
    assert segment.text == "Bonjour le monde"


def test_transcript_segment_low_confidence() -> None:
    """Test TranscriptSegment with low confidence score."""
    segment = TranscriptSegment(
        text="uncertain text",
        start_s=5.0,
        end_s=6.0,
        language="en",
        confidence=0.3,
    )
    assert segment.confidence == 0.3


def test_transcript_segment_immutable() -> None:
    """Test TranscriptSegment is frozen (immutable)."""
    segment = TranscriptSegment(
        text="test",
        start_s=0.0,
        end_s=1.0,
        language="en",
        confidence=1.0,
    )
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        segment.text = "modified"  # type: ignore[misc]


def test_transcript_segment_empty_text() -> None:
    """Test TranscriptSegment can have empty text."""
    segment = TranscriptSegment(
        text="",
        start_s=0.0,
        end_s=0.5,
        language="en",
        confidence=0.0,
    )
    assert segment.text == ""
    assert len(segment.text) == 0


def test_transcript_segment_multiline_text() -> None:
    """Test TranscriptSegment with multiline text."""
    segment = TranscriptSegment(
        text="First line\nSecond line\nThird line",
        start_s=0.0,
        end_s=10.0,
        language="en",
        confidence=0.9,
    )
    assert "\n" in segment.text
    assert segment.text.count("\n") == 2


def test_transcript_segment_duration_calculation() -> None:
    """Test calculating segment duration."""
    segment = TranscriptSegment(
        text="test",
        start_s=2.5,
        end_s=7.5,
        language="en",
        confidence=1.0,
    )
    duration = segment.end_s - segment.start_s
    assert duration == 5.0
