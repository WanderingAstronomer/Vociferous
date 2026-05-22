from __future__ import annotations

import json

import httpx

from src.refinement.providers import OpenAICompatibleRefinementProvider, describe_refinement_runtime


VALID_GROQ_KEY = "gsk_test_secret_123456789012345678901234567890"


def _json_response(payload: dict, status_code: int = 200, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(status_code, json=payload, headers=headers or {})


def test_lm_studio_chat_payload_uses_lm_studio_parameters(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "local-model"

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": "Corrected text"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = provider.refine(
        "corrected text",
        temperature=0.2,
        top_p=0.9,
        top_k=40,
        repetition_penalty=1.15,
        use_thinking=True,
        allow_skip=False,
    )

    assert result.content == "Corrected text"
    assert captured["model"] == "local-model"
    assert captured["max_tokens"]
    assert captured["top_k"] == 40
    assert captured["repeat_penalty"] == 1.15
    assert "max_completion_tokens" not in captured
    assert "/no_think" not in str(captured["messages"])


def test_groq_chat_payload_uses_groq_token_field_and_omits_local_knobs(fresh_settings) -> None:
    fresh_settings.refinement.provider = "groq"
    fresh_settings.refinement.groq.model_id = "llama-3.1-8b-instant"
    fresh_settings.refinement.groq.api_key = VALID_GROQ_KEY

    captured: dict[str, object] = {}
    captured_auth = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_auth
        captured_auth = request.headers.get("authorization", "")
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": "Groq text"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "groq")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = provider.refine(
        "groq text",
        temperature=0.2,
        top_p=0.9,
        top_k=40,
        repetition_penalty=1.15,
        use_thinking=False,
        allow_skip=False,
    )

    assert result.content == "Groq text"
    assert captured_auth == f"Bearer {VALID_GROQ_KEY}"
    assert captured["model"] == "llama-3.1-8b-instant"
    assert captured["max_completion_tokens"]
    assert "max_tokens" not in captured
    assert "top_k" not in captured
    assert "repeat_penalty" not in captured


def test_qwen_external_custom_generation_sends_no_think_when_thinking_disabled(fresh_settings) -> None:
    fresh_settings.refinement.provider = "groq"
    fresh_settings.refinement.groq.model_id = "qwen/qwen3-32b"
    fresh_settings.refinement.groq.api_key = VALID_GROQ_KEY

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": "Useful Title"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "groq")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = provider.generate_custom(
        system_prompt="title this",
        user_prompt="transcript text",
        max_tokens=30,
        temperature=0.4,
        use_thinking=False,
    )

    assert result.content == "Useful Title"
    assert "/no_think" in str(captured["messages"])


def test_qwen_external_custom_generation_omits_no_think_when_thinking_enabled(fresh_settings) -> None:
    fresh_settings.refinement.provider = "groq"
    fresh_settings.refinement.groq.model_id = "qwen/qwen3-32b"
    fresh_settings.refinement.groq.api_key = VALID_GROQ_KEY

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": "Useful Title"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "groq")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    provider.generate_custom(
        system_prompt="title this",
        user_prompt="transcript text",
        max_tokens=30,
        temperature=0.4,
        use_thinking=True,
    )

    assert "/no_think" not in str(captured["messages"])


def test_external_load_validates_connectivity_even_when_model_listing_disabled(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "local-model"
    fresh_settings.refinement.lm_studio.model_list_enabled = False

    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return _json_response({"data": [{"id": "local-model"}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    provider.load()

    assert requested_paths == ["/v1/models"]


def test_lm_studio_load_surfaces_server_unreachable(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "local-model"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    import pytest

    with pytest.raises(Exception, match="LM Studio is unreachable"):
        provider.load()


def test_list_models_parses_openai_compatible_response(fresh_settings) -> None:
    fresh_settings.refinement.lm_studio.model_id = "local-model"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        return _json_response({"data": [{"id": "one"}, {"id": "two", "object": "model"}, {"object": "ignored"}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    assert provider.list_models() == [{"id": "one", "object": "model"}, {"id": "two", "object": "model"}]


def test_external_runtime_summary_does_not_require_local_model(fresh_settings) -> None:
    fresh_settings.refinement.provider = "groq"
    fresh_settings.refinement.groq.model_id = "llama-3.1-8b-instant"
    fresh_settings.refinement.groq.api_key = VALID_GROQ_KEY

    summary = describe_refinement_runtime(fresh_settings)

    assert summary["provider"] == "groq"
    assert summary["model_id"] == "llama-3.1-8b-instant"
    assert summary["resolved_device"] == "external"
    assert summary["has_api_key"] is True


def test_groq_key_with_bearer_prefix_is_normalized_before_auth_header(fresh_settings) -> None:
    fresh_settings.refinement.provider = "groq"
    fresh_settings.refinement.groq.model_id = "llama-3.1-8b-instant"
    fresh_settings.refinement.groq.api_key = f"Bearer {VALID_GROQ_KEY}"

    captured_auth = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_auth
        captured_auth = request.headers.get("authorization", "")
        return _json_response({"data": [{"id": "llama-3.1-8b-instant"}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "groq")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    provider.list_models()

    assert captured_auth == f"Bearer {VALID_GROQ_KEY}"


def test_groq_key_shape_is_validated_before_request(fresh_settings) -> None:
    fresh_settings.refinement.provider = "groq"
    fresh_settings.refinement.groq.model_id = "llama-3.1-8b-instant"
    fresh_settings.refinement.groq.api_key = "gsk_too_short"

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "groq")

    import pytest

    with pytest.raises(ValueError, match="Groq API key looks invalid"):
        provider.list_models()