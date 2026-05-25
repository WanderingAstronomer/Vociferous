"""Transcription service package.

The legacy public surface continues to live in :mod:`src.services.transcription_service`.
This package houses the decomposed pieces that file delegates to.
"""

from src.services.transcription.post_process import (
    collapse_repeated_phrases,
    merge_segment_texts,
    needs_boundary_space,
    normalize_sentence_casing,
    post_process_transcription,
)

__all__ = [
    "collapse_repeated_phrases",
    "merge_segment_texts",
    "needs_boundary_space",
    "normalize_sentence_casing",
    "post_process_transcription",
]
