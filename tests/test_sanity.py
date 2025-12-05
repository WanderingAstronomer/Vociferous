from chatterbug.domain import AudioChunk, TranscriptSegment


def test_domain_types_constructable() -> None:
    chunk = AudioChunk(samples=b"", sample_rate=16000, channels=1, start_s=0.0, end_s=0.1)
    segment = TranscriptSegment(
        text="hello", start_s=0.0, end_s=0.1, language="en", confidence=0.9
    )
    assert chunk.sample_rate == 16000
    assert segment.text == "hello"
