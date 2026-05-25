"""
Tests for the TranscriptDB (raw sqlite3).

Verifies:
- Table creation
- CRUD operations
- Search
- WAL mode
"""

import pytest

from src.database.db import Transcript, TranscriptDB


@pytest.fixture
def db(tmp_path):
    """Create an in-memory-like temp DB for each test."""
    d = TranscriptDB(db_path=tmp_path / "test.db")
    yield d
    d.close()


class TestTranscriptCRUD:
    def test_add_and_retrieve(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Hello world", duration_ms=1000)
        assert t.id is not None
        assert t.raw_text == "Hello world"
        assert t.duration_ms == 1000

    def test_get_transcript(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Test", duration_ms=500)
        fetched = db.get_transcript(t.id)
        assert fetched is not None
        assert fetched.raw_text == "Test"

    def test_processing_provenance_is_persisted(self, db: TranscriptDB):
        transcript = db.add_transcript(
            raw_text="Hello world",
            duration_ms=1000,
            transcription_provider="groq",
            transcription_model_id="whisper-large-v3-turbo",
            transcription_resolved_device="external_api",
            transcription_compute_type="api",
            transcription_cpu_threads=0,
            transcription_prompt_text="Use medical terminology.",
            transcription_prompt_chars=24,
            transcription_prompt_words=3,
        )
        db.update_refinement_processing_context(
            transcript.id,
            refinement_time_ms=2100,
            refinement_provider="lm_studio",
            refinement_model_id="qwen3.5-27b",
            refinement_resolved_device="cuda",
            refinement_compute_type="float16",
            refinement_cpu_threads=8,
            refinement_gpu_layers=99,
            refinement_use_thinking=False,
            refinement_prompt_text="Preserve bullets and fix grammar.\n\nText:",
            refinement_prompt_chars=40,
            refinement_prompt_words=6,
            refinement_prompt_tokens=72,
            refinement_completion_tokens=38,
            refinement_total_tokens=110,
        )

        fetched = db.get_transcript(transcript.id)
        assert fetched is not None
        assert fetched.transcription_provider == "groq"
        assert fetched.transcription_model_id == "whisper-large-v3-turbo"
        assert fetched.transcription_resolved_device == "external_api"
        assert fetched.transcription_compute_type == "api"
        assert fetched.transcription_cpu_threads == 0
        assert fetched.transcription_prompt_text == "Use medical terminology."
        assert fetched.transcription_prompt_chars == 24
        assert fetched.transcription_prompt_words == 3
        assert fetched.refinement_provider == "lm_studio"
        assert fetched.refinement_model_id == "qwen3.5-27b"
        assert fetched.refinement_resolved_device == "cuda"
        assert fetched.refinement_compute_type == "float16"
        assert fetched.refinement_cpu_threads == 8
        assert fetched.refinement_gpu_layers == 99
        assert fetched.refinement_use_thinking is False
        assert fetched.refinement_prompt_text == "Preserve bullets and fix grammar.\n\nText:"
        assert fetched.refinement_prompt_chars == 40
        assert fetched.refinement_prompt_words == 6
        assert fetched.refinement_prompt_tokens == 72
        assert fetched.refinement_completion_tokens == 38
        assert fetched.refinement_total_tokens == 110

    def test_retranscription_provenance_is_persisted_separately(self, db: TranscriptDB):
        transcript = db.add_transcript(
            raw_text="Original raw text",
            normalized_text="Original normalized text",
            duration_ms=1000,
            transcription_provider="groq",
            transcription_model_id="whisper-large-v3-turbo",
            transcription_resolved_device="external_api",
            transcription_compute_type="api",
            transcription_prompt_text="Use medical terminology.",
            transcription_prompt_chars=24,
            transcription_prompt_words=3,
        )

        db.update_retranscription_processing_context(
            transcript.id,
            normalized_text="Retrancribed normalized text",
            retranscription_time_ms=1337,
            retranscription_provider="local_faster_whisper",
            retranscription_model_id="large-v3",
            retranscription_resolved_device="cuda",
            retranscription_compute_type="float16",
            retranscription_cpu_threads=6,
            retranscription_prompt_text="Prefer proper nouns.",
            retranscription_prompt_chars=20,
            retranscription_prompt_words=3,
        )

        fetched = db.get_transcript(transcript.id)
        assert fetched is not None
        assert fetched.normalized_text == "Retrancribed normalized text"
        assert fetched.transcription_provider == "groq"
        assert fetched.transcription_model_id == "whisper-large-v3-turbo"
        assert fetched.transcription_resolved_device == "external_api"
        assert fetched.retranscription_count == 1
        assert fetched.last_retranscription_at != ""
        assert fetched.last_retranscription_time_ms == 1337
        assert fetched.last_retranscription_provider == "local_faster_whisper"
        assert fetched.last_retranscription_model_id == "large-v3"
        assert fetched.last_retranscription_resolved_device == "cuda"
        assert fetched.last_retranscription_compute_type == "float16"
        assert fetched.last_retranscription_cpu_threads == 6
        assert fetched.last_retranscription_prompt_text == "Prefer proper nouns."
        assert fetched.last_retranscription_prompt_chars == 20
        assert fetched.last_retranscription_prompt_words == 3

    def test_get_nonexistent(self, db: TranscriptDB):
        assert db.get_transcript(9999) is None

    def test_delete(self, db: TranscriptDB):
        t = db.add_transcript(raw_text="Delete me", duration_ms=100)
        assert db.delete_transcript(t.id) is True
        assert db.get_transcript(t.id) is None

    def test_delete_nonexistent(self, db: TranscriptDB):
        assert db.delete_transcript(9999) is False

    def test_recent(self, db: TranscriptDB):
        for i in range(5):
            db.add_transcript(raw_text=f"Transcript {i}", duration_ms=100)
        recent, total = db.recent(limit=3)
        assert len(recent) == 3
        assert total == 5

    def test_recent_supports_boolean_tag_modes(self, db: TranscriptDB):
        work_tag = db.add_tag("Work")
        urgent_tag = db.add_tag("Urgent")
        personal_tag = db.add_tag("Personal")
        assert work_tag.id is not None
        assert urgent_tag.id is not None
        assert personal_tag.id is not None

        db.add_transcript(raw_text="work only", tag_ids=[work_tag.id])
        db.add_transcript(raw_text="urgent only", tag_ids=[urgent_tag.id])
        db.add_transcript(raw_text="work urgent", tag_ids=[work_tag.id, urgent_tag.id])
        db.add_transcript(raw_text="personal only", tag_ids=[personal_tag.id])
        db.add_transcript(raw_text="untagged")

        def texts_for_mode(mode: str) -> set[str]:
            transcripts, total = db.recent(tag_ids=[work_tag.id, urgent_tag.id], tag_mode=mode, limit=20)
            assert total == len(transcripts)
            return {transcript.raw_text for transcript in transcripts}

        assert texts_for_mode("or") == {"work only", "urgent only", "work urgent"}
        assert texts_for_mode("any") == {"work only", "urgent only", "work urgent"}
        assert texts_for_mode("and") == {"work urgent"}
        assert texts_for_mode("all") == {"work urgent"}
        assert texts_for_mode("not") == {"personal only", "untagged"}
        assert texts_for_mode("nand") == {"work only", "urgent only", "personal only", "untagged"}
        assert texts_for_mode("xor") == {"work only", "urgent only"}

        with pytest.raises(ValueError, match="tag_mode"):
            db.recent(tag_ids=[work_tag.id], tag_mode="nor")

    def test_transcript_count(self, db: TranscriptDB):
        assert db.transcript_count() == 0
        db.add_transcript(raw_text="One", duration_ms=100)
        db.add_transcript(raw_text="Two", duration_ms=100)
        assert db.transcript_count() == 2

    def test_shipped_prompts_are_prompt_records_not_transcript_data(self, db: TranscriptDB):
        prompt_tag = next(tag for tag in db.get_tags() if tag.name == "Prompt")
        prompts, total = db.recent(tag_ids=[prompt_tag.id], include_protected=True)

        assert total == 2
        assert {prompt.display_name for prompt in prompts} == {
            "Small Model Markdown Refinement Prompt",
            "Large Model Structured Markdown Prompt",
        }
        assert all(prompt.created_at == "" for prompt in prompts)
        assert all(not prompt.include_in_analytics for prompt in prompts)

    def test_search(self, db: TranscriptDB):
        db.add_transcript(raw_text="Python programming", duration_ms=100)
        db.add_transcript(raw_text="JavaScript development", duration_ms=100)
        results = db.search("python")
        assert len(results) == 1
        assert "Python" in results[0].raw_text

    def test_search_matches_display_name(self, db: TranscriptDB):
        titled = db.add_transcript(raw_text="Body text without the keyword", display_name="Launch Checklist", duration_ms=100)
        db.add_transcript(raw_text="Unrelated body", display_name="Meeting Notes", duration_ms=100)

        results = db.search("launch")

        assert [item.id for item in results] == [titled.id]
        assert db.search_count("launch") == 1

    def test_append_preserves_source_and_hides_child_from_default_queries(self, db: TranscriptDB):
        root = db.add_transcript(raw_text="Root text", duration_ms=1000, speech_duration_ms=900)
        source = db.add_transcript(raw_text="New segment", duration_ms=500, speech_duration_ms=450)

        root_id = db.append_to_transcript(root.id, source.id)

        assert root_id == root.id

        preserved_source = db.get_transcript(source.id)
        assert preserved_source is not None
        assert preserved_source.compound_root_id == root.id
        assert preserved_source.compound_order == 1

        updated_root = db.get_transcript(root.id)
        assert updated_root is not None
        assert updated_root.raw_text == "Root text\n\nNew segment"
        assert updated_root.duration_ms == 1500
        assert updated_root.speech_duration_ms == 1350
        assert any(tag.name == "Compound" for tag in updated_root.tags)

        visible_items, visible_total = db.recent(limit=10)
        visible_ids = {item.id for item in visible_items}
        assert root.id in visible_ids
        assert source.id not in visible_ids
        assert visible_total == 1
        assert db.transcript_count() == 1
        assert db.transcript_count(include_compound_children=True) == 2

    def test_search_excludes_hidden_compound_children_by_default(self, db: TranscriptDB):
        root = db.add_transcript(raw_text="Alpha", duration_ms=100)
        source = db.add_transcript(raw_text="Beta keyword", duration_ms=100)

        db.append_to_transcript(root.id, source.id)

        default_results = db.search("beta")
        assert [item.id for item in default_results] == [root.id]
        assert db.search_count("beta") == 1

        all_results = db.search("beta", include_compound_children=True)
        assert {item.id for item in all_results} == {root.id, source.id}
        assert db.search_count("beta", include_compound_children=True) == 2
