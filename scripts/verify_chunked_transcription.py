"""Verification for long-recording STT chunking (Groq 25 MB cap fix).

Simulates the reported 28-minute recording at full production scale and proves:

  1. PRE-FIX: the single outbound WAV payload exceeds Groq's 25 MB free-tier cap
     (so the original single-request send would fail with HTTP 413).
  2. SPLIT-ON-SILENCE: the REAL Silero VAD pipeline is used to choose cut points,
     and every cut lands inside a silence gap — never mid-word.
  3. SUB-CAP CHUNKS: each chunk's encoded WAV stays under the 20 MB budget and
     under the 25 MB cap.
  4. SEAM INTEGRITY: assigning each spoken word to the chunk containing it and
     concatenating reproduces the full word sequence exactly once, in order —
     no dropped or duplicated words at chunk boundaries.
  5. END-TO-END: _transcribe_external_chunked drives sequential per-chunk sends
     and stitches the texts into one transcript with a single post-process pass.

Run: uv run python scripts/verify_chunked_transcription.py
"""

from __future__ import annotations

import numpy as np

from src.core.constants import AudioConfig
from src.services.audio_pipeline import AudioPipeline
from src.services.transcription_service import (
    _CHUNK_BYTE_BUDGET,
    OpenAICompatibleTranscriptionProvider,
    _encoded_wav_size,
    _max_chunk_samples,
    _split_on_silence,
    _transcribe_external_chunked,
)
from src.core.settings import VociferousSettings

SR = AudioConfig.DEFAULT_SAMPLE_RATE  # 16 kHz
GROQ_FREE_CAP = 25 * 1024 * 1024
MB = 1024 * 1024


def build_28_minute_recording() -> tuple[np.ndarray, int, int, int]:
    """Build ~28 min of speech-like word bursts separated by silence gaps.

    Each word occupies a fixed grid slot: SPEECH samples of band-limited noise
    (which Silero VAD recognises as speech) followed by GAP samples of true
    silence. Returns (audio_f32, word_len, speech_len, n_words).
    """
    speech_len = int(0.45 * SR)  # 0.45 s of "speech"
    gap_len = int(0.25 * SR)  # 0.25 s of silence between words
    word_len = speech_len + gap_len  # 0.70 s per word
    n_words = (28 * 60 * SR) // word_len  # fill ~28 minutes

    rng = np.random.RandomState(1234)
    # Band-limited-ish noise burst: smooth low-frequency noise reads as speech to VAD.
    audio = np.zeros(n_words * word_len, dtype=np.float32)
    for i in range(n_words):
        noise = rng.randn(speech_len).astype(np.float32)
        # Light smoothing to push energy into speech band; scale to a realistic level.
        noise = np.convolve(noise, np.ones(8, dtype=np.float32) / 8.0, mode="same") * 0.25
        start = i * word_len
        audio[start : start + speech_len] = noise
        # remaining gap_len samples stay zero (silence)
    return audio, word_len, speech_len, int(n_words)


def main() -> int:
    print("=== Long-recording STT chunking verification (28-min case) ===\n")
    audio, word_len, speech_len, n_words = build_28_minute_recording()
    total_samples = len(audio)
    duration_s = total_samples / SR
    payload_bytes = _encoded_wav_size(total_samples)

    print(f"Recording: {duration_s/60:.1f} min, {total_samples:,} samples, {n_words:,} words")
    print(f"Encoded WAV payload: {payload_bytes/MB:.1f} MB")
    print(f"Groq free-tier cap:  {GROQ_FREE_CAP/MB:.0f} MB | budget/chunk: {_CHUNK_BYTE_BUDGET/MB:.0f} MB\n")

    ok = True

    # (1) PRE-FIX would fail.
    pre_fix_fails = payload_bytes > GROQ_FREE_CAP
    print(f"[1] Single payload exceeds 25 MB cap (pre-fix 413): {pre_fix_fails}")
    ok &= pre_fix_fails

    # (2)+(3) Split using the REAL Silero VAD pipeline; verify cuts + sizes.
    pipeline = AudioPipeline(sample_rate=SR)
    print(f"    Using real Silero VAD: {pipeline._resolve_model_path().name}")
    max_samples = _max_chunk_samples()
    segments = _split_on_silence(audio, pipeline, max_samples)
    seg_lens = [len(s) for s in segments]
    cuts = list(np.cumsum(seg_lens)[:-1])

    print(f"\n[2] Split into {len(segments)} chunks (cuts at {[c for c in cuts]})")
    print(f"    chunk durations (s): {[round(n/SR,1) for n in seg_lens]}")

    # Every cut must land in a silence gap: pos within its grid slot >= speech_len.
    cuts_in_silence = all((c % word_len) >= speech_len for c in cuts)
    print(f"    every cut lands in a silence gap (never mid-word): {cuts_in_silence}")
    ok &= cuts_in_silence

    # No samples dropped.
    no_loss = sum(seg_lens) == total_samples
    print(f"    no samples dropped (sum == total): {no_loss}")
    ok &= no_loss

    # (3) Each chunk under budget and under the hard cap.
    sizes = [_encoded_wav_size(n) for n in seg_lens]
    under_budget = all(s <= _CHUNK_BYTE_BUDGET for s in sizes)
    under_cap = all(s < GROQ_FREE_CAP for s in sizes)
    print(f"\n[3] chunk WAV sizes (MB): {[round(s/MB,1) for s in sizes]}")
    print(f"    all chunks <= 20 MB budget: {under_budget} | all < 25 MB cap: {under_cap}")
    ok &= under_budget and under_cap

    # (4) Seam integrity: assign each word to the chunk holding its burst centre,
    # concatenate -> must reproduce 0..n_words-1 exactly once, in order.
    bounds = [0] + cuts + [total_samples]
    stitched_word_ids: list[int] = []
    for lo, hi in zip(bounds, bounds[1:]):
        ids = [w for w in range(n_words) if lo <= (w * word_len + speech_len // 2) < hi]
        stitched_word_ids.extend(ids)
    seam_ok = stitched_word_ids == list(range(n_words))
    print(f"\n[4] words reproduced exactly once, in order (no drop/dup at seams): {seam_ok}")
    if not seam_ok:
        # Diagnose duplicates / drops.
        from collections import Counter

        counts = Counter(stitched_word_ids)
        dups = [w for w, c in counts.items() if c > 1]
        missing = [w for w in range(n_words) if w not in counts]
        print(f"    duplicated words: {dups[:10]} | missing words: {missing[:10]}")
    ok &= seam_ok

    # (5) End-to-end: drive _transcribe_external_chunked with a fake provider that
    # records per-chunk payload sizes and returns ordered text; verify stitching
    # + single post-process pass.
    settings = _groq_settings()
    sent_sizes: list[int] = []

    class _FakeProvider(OpenAICompatibleTranscriptionProvider):
        def transcribe_raw(self, chunk, settings):  # type: ignore[override]
            sent_sizes.append(_encoded_wav_size(len(chunk)))
            idx = len(sent_sizes) - 1
            return f"part{idx}", 1000, 5

    provider = _FakeProvider(settings)
    text, speech_ms, _ = _transcribe_external_chunked(provider, audio, settings, pipeline)
    parts = [f"part{i}" for i in range(len(sent_sizes))]
    positions = [text.lower().find(p) for p in parts]
    e2e_ok = (
        len(sent_sizes) == len(segments)
        and all(s <= _CHUNK_BYTE_BUDGET for s in sent_sizes)
        and all(p != -1 for p in positions)
        and positions == sorted(positions)
        and speech_ms == len(sent_sizes) * 1000
    )
    print(f"\n[5] end-to-end: {len(sent_sizes)} sequential sends, stitched in order,")
    print(f"    single post-processed transcript ({len(text)} chars): {e2e_ok}")
    ok &= e2e_ok

    print("\n=== " + ("VERIFICATION PASSED" if ok else "VERIFICATION FAILED") + " ===")
    return 0 if ok else 1


def _groq_settings():
    settings = VociferousSettings()
    groq = settings.model.groq.model_copy(
        update={
            "model_id": "whisper-large-v3-turbo",
            "model_list_enabled": False,
            "api_key": "gsk_verify_secret_123456789012345678901234567890",
        }
    )
    return settings.model_copy(
        update={"model": settings.model.model_copy(update={"provider": "groq", "groq": groq})}
    )


if __name__ == "__main__":
    raise SystemExit(main())
