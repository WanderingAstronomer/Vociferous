"""Test TranscriptSink implementations."""
from pathlib import Path

import pytest

from vociferous.cli.sinks import FileSink, StdoutSink, CompositeSink
from vociferous.domain.model import TranscriptSegment, TranscriptionResult


@pytest.fixture
def sample_segment() -> TranscriptSegment:
    """Create a sample transcript segment."""
    return TranscriptSegment(
        text="Hello world",
        start_s=0.0,
        end_s=1.5,
        language="en",
        confidence=0.95,
    )


@pytest.fixture
def sample_result() -> TranscriptionResult:
    """Create a sample transcription result."""
    return TranscriptionResult(
        text="Hello world this is a test",
        segments=(
            TranscriptSegment(text="Hello world", start_s=0.0, end_s=1.5, language="en", confidence=0.95),
            TranscriptSegment(text="this is a test", start_s=1.5, end_s=3.0, language="en", confidence=0.92),
        ),
        model_name="openai/whisper-large-v3-turbo",
        device="cpu",
        precision="int8",
        engine="whisper_turbo",
        duration_s=3.0,
        warnings=(),
    )


def test_stdout_sink_collects_segments(sample_segment: TranscriptSegment, sample_result: TranscriptionResult) -> None:
    """Test StdoutSink collects segments."""
    sink = StdoutSink()
    sink.handle_segment(sample_segment)
    assert len(sink._segments) == 1
    assert sink._segments[0].text == "Hello world"
    
    sink.complete(sample_result)
    # complete() doesn't clear segments, just outputs


def test_file_sink_writes_transcript(tmp_path: Path, sample_segment: TranscriptSegment, sample_result: TranscriptionResult) -> None:
    """Test FileSink writes transcript to file."""
    output_file = tmp_path / "transcript.txt"
    sink = FileSink(output_file)
    
    sink.handle_segment(sample_segment)
    assert not output_file.exists()  # Not written until complete
    
    sink.complete(sample_result)
    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert content == "Hello world this is a test"


def test_file_sink_overwrites_existing_file(tmp_path: Path, sample_result: TranscriptionResult) -> None:
    """Test FileSink overwrites existing files."""
    output_file = tmp_path / "transcript.txt"
    output_file.write_text("old content", encoding="utf-8")
    
    sink = FileSink(output_file)
    sink.complete(sample_result)
    
    content = output_file.read_text(encoding="utf-8")
    assert content == "Hello world this is a test"
    assert "old content" not in content


def test_composite_sink_fans_out_to_multiple_sinks(tmp_path: Path, sample_segment: TranscriptSegment, sample_result: TranscriptionResult) -> None:
    """Test CompositeSink distributes to all child sinks."""
    file1 = tmp_path / "out1.txt"
    file2 = tmp_path / "out2.txt"
    
    sink1 = FileSink(file1)
    sink2 = FileSink(file2)
    composite = CompositeSink([sink1, sink2])
    
    composite.handle_segment(sample_segment)
    composite.complete(sample_result)
    
    assert file1.exists()
    assert file2.exists()
    assert file1.read_text(encoding="utf-8") == "Hello world this is a test"
    assert file2.read_text(encoding="utf-8") == "Hello world this is a test"


def test_composite_sink_with_empty_list() -> None:
    """Test CompositeSink handles empty sink list."""
    composite = CompositeSink([])
    segment = TranscriptSegment(text="test", start_s=0.0, end_s=1.0, language="en", confidence=1.0)
    result = TranscriptionResult(
        text="test",
        segments=(segment,),
        model_name="test",
        device="cpu",
        precision="int8",
        engine="whisper_turbo",
        duration_s=1.0,
    )
    
    # Should not raise
    composite.handle_segment(segment)
    composite.complete(result)
