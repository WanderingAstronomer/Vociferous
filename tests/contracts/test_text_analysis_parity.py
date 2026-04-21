"""Contract test: backend and frontend filler-word lists must stay in sync.

The Python list lives in `src/core/text_analysis.py` (the single backend source
of truth — see ISS-108). The TypeScript mirror lives in
`frontend/src/lib/textAnalysis.ts`. If either side changes, this test fails
until both are updated.
"""

from __future__ import annotations

import re
from pathlib import Path

from src.core.text_analysis import FILLER_MULTI, FILLER_SINGLE

_FRONTEND_FILE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "textAnalysis.ts"


def _extract_set(source: str, name: str) -> set[str]:
    """Pull a `new Set([...])` literal out of the TS source by variable name."""
    pattern = rf"const\s+{name}\s*=\s*new\s+Set\(\s*\[(.*?)\]\s*\)"
    match = re.search(pattern, source, re.DOTALL)
    assert match, f"Could not find {name} in {_FRONTEND_FILE}"
    body = match.group(1)
    return {item.strip().strip('"').strip("'") for item in body.split(",") if item.strip()}


def _extract_array(source: str, name: str) -> list[str]:
    """Pull a `const NAME = [...]` array literal out of the TS source."""
    pattern = rf"const\s+{name}\s*=\s*\[(.*?)\]"
    match = re.search(pattern, source, re.DOTALL)
    assert match, f"Could not find {name} in {_FRONTEND_FILE}"
    body = match.group(1)
    return [item.strip().strip('"').strip("'") for item in body.split(",") if item.strip()]


def test_filler_single_lists_match() -> None:
    source = _FRONTEND_FILE.read_text(encoding="utf-8")
    ts_set = _extract_set(source, "FILLER_SINGLE")
    assert ts_set == set(FILLER_SINGLE), (
        "Frontend FILLER_SINGLE drifted from src/core/text_analysis.py FILLER_SINGLE. "
        f"Backend-only: {set(FILLER_SINGLE) - ts_set}. Frontend-only: {ts_set - set(FILLER_SINGLE)}."
    )


def test_filler_multi_lists_match() -> None:
    source = _FRONTEND_FILE.read_text(encoding="utf-8")
    ts_list = _extract_array(source, "FILLER_MULTI")
    assert tuple(ts_list) == FILLER_MULTI, (
        "Frontend FILLER_MULTI drifted from src/core/text_analysis.py FILLER_MULTI. "
        f"Backend: {FILLER_MULTI}. Frontend: {tuple(ts_list)}."
    )
