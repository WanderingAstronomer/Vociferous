"""Pure post-processing helpers for ASR transcription output.

These functions are deterministic and have no side effects beyond logging.
They were previously embedded in :mod:`src.services.transcription_service`
and are extracted here so they can be tested, reused, and reasoned about
independently of the I/O-heavy ASR pipeline.
"""

from __future__ import annotations

import logging
import re

from src.core.settings import VociferousSettings

logger = logging.getLogger(__name__)


def collapse_repeated_phrases(
    text: str,
    min_phrase_words: int = 3,
    max_phrase_words: int = 30,
) -> str:
    """Detect and collapse runs of consecutive repeated phrases.

    Whisper (especially v3) occasionally enters a generative loop, emitting
    the same phrase or sentence many times consecutively. This routine finds
    any n-gram (between ``min_phrase_words`` and ``max_phrase_words`` words)
    that repeats three or more times in a row and collapses it to a single
    occurrence.
    """
    if not text:
        return text

    words = text.split()
    if len(words) < min_phrase_words * 3:
        return text

    result = text
    for phrase_len in range(min(max_phrase_words, len(words) // 3), min_phrase_words - 1, -1):
        result_words = result.split()
        i = 0
        cleaned_words: list[str] = []
        while i < len(result_words):
            if i + phrase_len * 3 <= len(result_words):
                phrase = result_words[i : i + phrase_len]
                repeats = 1
                j = i + phrase_len
                while j + phrase_len <= len(result_words):
                    candidate = result_words[j : j + phrase_len]
                    if candidate == phrase:
                        repeats += 1
                        j += phrase_len
                    else:
                        break
                if repeats >= 3:
                    logger.warning(
                        "Collapsed %d consecutive repetitions of %d-word phrase: '%s'",
                        repeats,
                        phrase_len,
                        " ".join(phrase[:8]) + ("..." if phrase_len > 8 else ""),
                    )
                    cleaned_words.extend(phrase)
                    i = j
                    continue
            cleaned_words.append(result_words[i])
            i += 1
        result = " ".join(cleaned_words)

    return result


def needs_boundary_space(left_text: str, right_text: str) -> bool:
    """Return True when a single separator space should be inserted."""
    if not left_text or not right_text:
        return False

    left_char = left_text[-1]
    right_char = right_text[0]

    if left_char.isspace() or right_char.isspace():
        return False

    if left_char.isalnum() and right_char.isalnum():
        return True

    if left_char in ".!?;:," and right_char.isalnum():
        return True

    return False


def merge_segment_texts(segment_texts: list[str]) -> str:
    """Merge ASR segment text with boundary-aware whitespace handling."""
    merged = ""

    for chunk in segment_texts:
        if not chunk:
            continue

        if not merged:
            merged = chunk
            continue

        if needs_boundary_space(merged, chunk):
            merged += " " + chunk.lstrip()
        else:
            merged += chunk

    return merged.strip()


def normalize_sentence_casing(text: str) -> str:
    """Capitalize the first alphabetical character of each sentence."""
    if not text:
        return text

    chars = list(text)
    should_capitalize = True

    for i, char in enumerate(chars):
        if char.isalpha():
            if should_capitalize:
                chars[i] = char.upper()
                should_capitalize = False
            continue

        if char in ".!?":
            should_capitalize = True

    return "".join(chars)


def post_process_transcription(
    transcription: str | None,
    settings: VociferousSettings,
) -> str:
    """Apply deterministic post-processing to raw ASR output."""
    if not transcription:
        return ""

    result = transcription.strip()
    result = collapse_repeated_phrases(result)
    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"\s+([,.;:!?])", r"\1", result)
    result = re.sub(r"(\.\.\.)([A-Za-z])", r"\1 \2", result)
    result = re.sub(r"(?<!\d)\.([A-Za-z])", r". \1", result)
    result = re.sub(r"([!?;:,])([A-Za-z])", r"\1 \2", result)
    result = normalize_sentence_casing(result)

    if settings.output.add_trailing_space:
        result += " "

    return result
