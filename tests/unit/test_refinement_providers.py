from __future__ import annotations

import json

import httpx
import pytest

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


def test_lm_studio_qwopus_refinement_uses_canonical_thinking_suppression(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "qwopus3.6-27b-v2-mtp"

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": "Edited text"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = provider.refine(
        "unedited text",
        temperature=0.2,
        top_p=0.9,
        top_k=20,
        repetition_penalty=1.0,
        use_thinking=False,
        allow_skip=False,
    )

    assert result.content == "Edited text"
    # Canonical Qwen3 mechanism: chat_template_kwargs.enable_thinking=False pre-fills
    # an empty <think></think> block so the model structurally cannot reason.
    assert captured["chat_template_kwargs"] == {"enable_thinking": False}
    # reasoning_effort=none is the parallel mechanism for providers that honor it.
    assert captured["reasoning_effort"] == "none"
    # /no_think is still injected as a belt-and-suspenders fallback for custom
    # merges whose chat templates ignore enable_thinking.
    assert "/no_think" in str(captured["messages"])
    # JSON schema must NOT be forced for Qwen3-family — it conflicts with the
    # thinking flow and reliably caused empty-content + reasoning-only hangs.
    assert "response_format" not in captured


def test_lm_studio_gpt_oss_extracts_schema_text_from_reasoning_content(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "openai/gpt-oss-20b"

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response(
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning_content": '{"text": "This is the edited text."}',
                        },
                        "finish_reason": "stop",
                    }
                ]
            }
        )

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = provider.refine(
        "this are the edited text",
        temperature=0.2,
        top_p=0.9,
        top_k=20,
        repetition_penalty=1.0,
        use_thinking=False,
        allow_skip=False,
    )

    assert result.content == "This is the edited text."
    assert result.reasoning is None
    assert captured["response_format"]


def test_lm_studio_gpt_oss_extracts_schema_text_from_content(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "openai/gpt-oss-20b"

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": '{"text": "Useful Title"}'}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = provider.generate_custom(
        system_prompt="title this",
        user_prompt="transcript text",
        max_tokens=30,
        temperature=0.4,
        use_thinking=False,
    )

    assert result.content == "Useful Title"
    assert result.reasoning is None
    assert captured["max_tokens"] == 128


def test_lm_studio_chat_response_preserves_reasoning_content(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "local-model"

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "choices": [
                    {
                        "message": {
                            "content": "Edited text",
                            "reasoning_content": "Internal draft notes",
                        }
                    }
                ]
            }
        )

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = provider.refine(
        "unedited text",
        temperature=0.2,
        top_p=0.9,
        top_k=20,
        repetition_penalty=1.0,
        use_thinking=False,
        allow_skip=False,
    )

    assert result.content == "Edited text"
    assert result.reasoning == "Internal draft notes"


def test_lm_studio_refinement_adds_token_budget_when_thinking_enabled(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "qwen3-local"

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": "Edited text"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    provider.refine(
        "short text",
        temperature=0.2,
        top_p=0.9,
        top_k=20,
        repetition_penalty=1.0,
        use_thinking=True,
        allow_skip=False,
    )

    assert captured["max_tokens"] == 2304
    assert "/no_think" not in str(captured["messages"])
    assert captured["chat_template_kwargs"] == {"enable_thinking": True}
    assert captured["reasoning_effort"] == "medium"


def test_lm_studio_non_reasoning_model_omits_reasoning_params(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "gemma-4-26b-a4b-it-ultra-uncensored-heretic"

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": "Edited text"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    provider.refine(
        "unedited text",
        temperature=0.2,
        top_p=0.9,
        top_k=20,
        repetition_penalty=1.0,
        use_thinking=False,
        allow_skip=False,
    )

    assert "chat_template_kwargs" not in captured
    assert "reasoning_effort" not in captured
    assert "response_format" not in captured


def test_groq_sets_reasoning_format_parsed_for_every_request(fresh_settings) -> None:
    fresh_settings.refinement.provider = "groq"
    fresh_settings.refinement.groq.model_id = "llama-3.1-8b-instant"
    fresh_settings.refinement.groq.api_key = VALID_GROQ_KEY

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": "Groq text"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "groq")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    provider.refine(
        "groq text",
        temperature=0.2,
        top_p=0.9,
        top_k=0,
        repetition_penalty=1.0,
        use_thinking=False,
        allow_skip=False,
    )

    assert captured["reasoning_format"] == "parsed"
    # llama-3.1 is not a reasoning model, so no effort param is sent.
    assert "reasoning_effort" not in captured


def test_groq_gpt_oss_sets_reasoning_effort_per_thinking_mode(fresh_settings) -> None:
    fresh_settings.refinement.provider = "groq"
    fresh_settings.refinement.groq.model_id = "openai/gpt-oss-120b"
    fresh_settings.refinement.groq.api_key = VALID_GROQ_KEY

    seen_efforts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        seen_efforts.append(str(payload.get("reasoning_effort", "<missing>")))
        return _json_response({"choices": [{"message": {"content": "ok"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "groq")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    provider.refine(
        "text",
        temperature=0.2,
        top_p=0.9,
        top_k=0,
        repetition_penalty=1.0,
        use_thinking=False,
        allow_skip=False,
    )
    provider.refine(
        "text",
        temperature=0.2,
        top_p=0.9,
        top_k=0,
        repetition_penalty=1.0,
        use_thinking=True,
        allow_skip=False,
    )

    assert seen_efforts == ["none", "medium"]


def test_groq_does_not_send_lm_studio_chat_template_kwargs(fresh_settings) -> None:
    fresh_settings.refinement.provider = "groq"
    fresh_settings.refinement.groq.model_id = "qwen/qwen3-32b"
    fresh_settings.refinement.groq.api_key = VALID_GROQ_KEY

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content.decode("utf-8")))
        return _json_response({"choices": [{"message": {"content": "ok"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "groq")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    provider.refine(
        "groq qwen3 refine",
        temperature=0.2,
        top_p=0.9,
        top_k=0,
        repetition_penalty=1.0,
        use_thinking=False,
        allow_skip=False,
    )

    # chat_template_kwargs is an LM Studio passthrough; Groq surfaces thinking
    # control through reasoning_effort and reasoning_format instead.
    assert "chat_template_kwargs" not in captured
    assert captured["reasoning_effort"] == "none"
    assert captured["reasoning_format"] == "parsed"


def test_lm_studio_reasoning_only_refinement_raises_instead_of_returning_original(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "qwopus3.6-27b-v2-mtp"

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning_content": "I am still thinking instead of answering.",
                        },
                        "finish_reason": "length",
                    }
                ]
            }
        )

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(RuntimeError, match="reasoning only"):
        provider.refine(
            "original text",
            temperature=0.2,
            top_p=0.9,
            top_k=20,
            repetition_penalty=1.0,
            use_thinking=False,
            allow_skip=False,
        )


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

    with pytest.raises(Exception, match="LM Studio is unreachable"):
        provider.load()


def test_lm_studio_refine_surfaces_timeout_as_stalled_server(fresh_settings) -> None:
    import pytest

    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "local-model"
    fresh_settings.refinement.lm_studio.timeout_seconds = 7.5

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(Exception, match=r"did not respond within 7.5s .*busy or stalled"):
        provider.refine(
            "needs fixing",
            temperature=0.2,
            top_p=0.9,
            top_k=40,
            repetition_penalty=1.15,
            use_thinking=False,
            allow_skip=False,
        )


def test_lm_studio_large_refine_scales_read_timeout(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "local-model"
    fresh_settings.refinement.lm_studio.timeout_seconds = 120.0

    captured_timeout: dict[str, float] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        timeout = request.extensions.get("timeout", {})
        captured_timeout.update(timeout)
        return _json_response({"choices": [{"message": {"content": "Corrected text"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = provider.refine(
        "word " * 2000,
        temperature=0.2,
        top_p=0.9,
        top_k=40,
        repetition_penalty=1.15,
        use_thinking=False,
        allow_skip=False,
    )

    assert result.content == "Corrected text"
    assert captured_timeout["read"] > 120.0
    assert captured_timeout["connect"] == 5.0
    assert captured_timeout["write"] == 30.0
    assert captured_timeout["pool"] == 5.0


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

    with pytest.raises(ValueError, match="Groq API key looks invalid"):
        provider.list_models()


def test_groq_refine_retries_with_smaller_budget_after_413(fresh_settings) -> None:
    fresh_settings.refinement.provider = "groq"
    fresh_settings.refinement.groq.model_id = "openai/gpt-oss-120b"
    fresh_settings.refinement.groq.api_key = VALID_GROQ_KEY
    fresh_settings.refinement.groq.max_output_tokens = 512

    seen_budgets: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        budget = int(payload["max_completion_tokens"])
        seen_budgets.append(budget)
        if len(seen_budgets) == 1:
            return _json_response({"error": {"message": "request too large"}}, status_code=413)
        return _json_response({"choices": [{"message": {"content": "Retried successfully"}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "groq")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    result = provider.refine(
        "word " * 250,
        temperature=0.2,
        top_p=0.9,
        top_k=0,
        repetition_penalty=1.0,
        use_thinking=False,
        allow_skip=False,
    )

    assert result.content == "Retried successfully"
    assert seen_budgets == [512, 256]


def test_external_refine_raises_when_provider_returns_empty_content(fresh_settings) -> None:
    fresh_settings.refinement.provider = "lm_studio"
    fresh_settings.refinement.lm_studio.model_id = "local-model"

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response({"choices": [{"message": {"content": "   "}}]})

    provider = OpenAICompatibleRefinementProvider(fresh_settings, "lm_studio")
    provider._client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(Exception, match="returned empty refinement output"):
        provider.refine(
            "needs fixing",
            temperature=0.2,
            top_p=0.9,
            top_k=40,
            repetition_penalty=1.15,
            use_thinking=False,
            allow_skip=False,
        )

