"""Real-world audio utilities tests focused on chunking."""

from __future__ import annotations

from vociferous.audio.utilities import chunk_pcm_bytes


class TestPCMChunking:
    """PCM data chunking logic."""

    def test_chunk_pcm_single_chunk(self) -> None:
        """Single chunk PCM splits into one chunk."""
        # 100ms of PCM16 at 16kHz mono = 3200 bytes
        pcm = b"\x00" * 3200
        chunks = list(
            chunk_pcm_bytes(
                pcm,
                sample_rate=16000,
                channels=1,
                chunk_ms=100,
                sample_width_bytes=2,
            )
        )
        assert len(chunks) == 1
        assert chunks[0].samples == pcm

    def test_chunk_pcm_multiple_chunks(self) -> None:
        """Multiple chunks PCM splits correctly."""
        # 300ms total = 3 x 100ms chunks = 9600 bytes
        pcm = b"\x00" * 9600
        chunks = list(
            chunk_pcm_bytes(
                pcm,
                sample_rate=16000,
                channels=1,
                chunk_ms=100,
                sample_width_bytes=2,
            )
        )
        assert len(chunks) == 3
        for chunk in chunks:
            assert len(chunk.samples) == 3200

    def test_chunk_pcm_preserves_data(self) -> None:
        """Chunking preserves original data in order."""
        # Create identifiable data: each chunk has incrementing pattern
        pcm = bytes(range(256)) * 40  # 10240 bytes = 320ms at 16kHz
        chunks = list(
            chunk_pcm_bytes(
                pcm,
                sample_rate=16000,
                channels=1,
                chunk_ms=100,
                sample_width_bytes=2,
            )
        )
        
        # Reconstruct and verify
        reconstructed = b"".join(chunk.samples for chunk in chunks)
        assert reconstructed == pcm

    def test_chunk_pcm_sets_timestamps(self) -> None:
        """Chunks have correct start and end timestamps."""
        pcm = b"\x00" * 9600  # 300ms at 16kHz mono
        chunks = list(
            chunk_pcm_bytes(
                pcm,
                sample_rate=16000,
                channels=1,
                chunk_ms=100,
                sample_width_bytes=2,
            )
        )
        
        assert len(chunks) == 3
        assert abs(chunks[0].start_s - 0.0) < 0.0001
        assert abs(chunks[0].end_s - 0.1) < 0.0001
        assert abs(chunks[1].start_s - 0.1) < 0.0001
        assert abs(chunks[1].end_s - 0.2) < 0.0001
        assert abs(chunks[2].start_s - 0.2) < 0.0001
        assert abs(chunks[2].end_s - 0.3) < 0.0001

    def test_chunk_pcm_stereo(self) -> None:
        """Stereo PCM chunks correctly."""
        # 200ms stereo = 12800 bytes = 2 x 100ms chunks
        pcm = b"\x00" * 12800
        chunks = list(
            chunk_pcm_bytes(
                pcm,
                sample_rate=16000,
                channels=2,
                chunk_ms=100,
                sample_width_bytes=2,
            )
        )
        assert len(chunks) == 2
        for chunk in chunks:
            assert len(chunk.samples) == 6400
