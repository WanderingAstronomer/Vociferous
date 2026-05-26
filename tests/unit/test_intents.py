from __future__ import annotations

import pytest

from src.core.intents.definitions import (
    BatchDeleteTranscriptsIntent,
    BulkRefineTranscriptsIntent,
    RefineTranscriptIntent,
    UpdateConfigIntent,
    thaw_value,
)


def test_batch_delete_transcript_ids_are_tupled_from_json_lists() -> None:
    ids = [1, 2]
    intent = BatchDeleteTranscriptsIntent(transcript_ids=ids)

    ids.append(3)

    assert intent.transcript_ids == (1, 2)


def test_bulk_refine_transcript_ids_are_tupled_from_json_lists() -> None:
    ids = [4, 5]
    intent = BulkRefineTranscriptsIntent(transcript_ids=ids, level=2)

    ids.append(6)

    assert intent.transcript_ids == (4, 5)


def test_refine_level_validation_still_rejects_invalid_levels() -> None:
    with pytest.raises(ValueError, match="level must be an integer between 1 and 5"):
        RefineTranscriptIntent(level=0)

    with pytest.raises(ValueError, match="level must be an integer between 1 and 5"):
        BulkRefineTranscriptsIntent(level=6)


def test_update_config_intent_freezes_nested_settings_payload() -> None:
    payload = {"user": {"name": "Drew"}, "refinement": {"invariants": ["one"]}}
    intent = UpdateConfigIntent(settings=payload)

    payload["user"]["name"] = "Mutated"
    payload["refinement"]["invariants"].append("two")

    assert intent.settings["user"]["name"] == "Drew"
    assert intent.settings["refinement"]["invariants"] == ("one",)
    with pytest.raises(TypeError):
        intent.settings["user"]["name"] = "Nope"


def test_thaw_value_returns_plain_containers_for_settings_merge() -> None:
    intent = UpdateConfigIntent(settings={"refinement": {"invariants": ["one"]}})

    thawed = thaw_value(intent.settings)

    assert thawed == {"refinement": {"invariants": ["one"]}}
    thawed["refinement"]["invariants"].append("two")
    assert intent.settings["refinement"]["invariants"] == ("one",)
