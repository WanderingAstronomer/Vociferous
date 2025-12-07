from vociferous.audio.decoder import DecodedAudio, _chunk_pcm_bytes


def test_chunk_pcm_bytes_splits_audio() -> None:
    # 1 second mono 16kHz int16 -> 32000 bytes
    audio = DecodedAudio(samples=b"\x00" * 32000, sample_rate=16000, channels=1, duration_s=1.0)
    chunks = list(_chunk_pcm_bytes(audio, chunk_ms=250))
    assert len(chunks) == 4
    assert chunks[0].start_s == 0.0
    assert chunks[-1].end_s == 1.0
