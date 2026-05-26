from __future__ import annotations

import re
from pathlib import Path

from src.core.settings import RefinementSettings

_REFINEMENT_CARD = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "components" / "RefinementCard.svelte"


def test_refinement_card_default_slm_matches_backend_default() -> None:
    source = _REFINEMENT_CARD.read_text(encoding="utf-8")
    match = re.search(r'const\s+DEFAULT_SLM_MODEL_ID\s*=\s*["\']([^"\']+)["\']', source)

    assert match, f"Could not find DEFAULT_SLM_MODEL_ID in {_REFINEMENT_CARD}"
    assert match.group(1) == RefinementSettings().model_id
