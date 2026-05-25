"""OpenAI-compatible HTTP refinement provider for LM Studio and Groq."""

from __future__ import annotations

import json
import logging
import time

import httpx

from src.core.secret_store import get_provider_api_key, normalize_provider_api_key, validate_provider_api_key
from src.core.settings import VociferousSettings
from src.refinement.engine import RefinementEngine
from src.refinement.output_parser import GenerationResult, parse_generation_output
from src.refinement.prompt_builder import PromptBuilder
from src.refinement.providers.capabilities import (
    TEXT_RESPONSE_FORMAT,
    ProviderCapabilities,
    resolve_capabilities,
)
from src.refinement.providers.contracts import ProviderRequestError
from src.refinement.providers.runtime import api_key_from_env, describe_refinement_runtime

logger = logging.getLogger(__name__)


class OpenAICompatibleRefinementProvider:
    """OpenAI-compatible HTTP refinement provider for LM Studio and Groq."""

    _CONNECT_TIMEOUT_SECONDS = 5.0
    _POOL_TIMEOUT_SECONDS = 5.0
    _WRITE_TIMEOUT_SECONDS = 30.0
    _LM_STUDIO_LONG_PROMPT_WORD_THRESHOLD = 600
    _LM_STUDIO_LONG_COMPLETION_TOKEN_THRESHOLD = 1024
    _LM_STUDIO_PROMPT_WORDS_PER_SECOND = 40.0
    _LM_STUDIO_GENERATION_TOKENS_PER_SECOND = 12.0
    _LM_STUDIO_MAX_READ_TIMEOUT_SECONDS = 900.0

    def __init__(self, settings: VociferousSettings, provider_id: str) -> None:
        if provider_id not in {"lm_studio", "groq"}:
            raise ValueError(f"Unsupported OpenAI-compatible provider: {provider_id}")
        self._settings = settings
        self._provider_id = provider_id
        self._provider_settings = getattr(settings.refinement, provider_id)
        self._client: httpx.Client | None = None
        self._runtime_summary = describe_refinement_runtime(settings)
        self._last_usage: dict[str, object] | None = None
        self._last_rate_limit: dict[str, str] = {}

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def load(self) -> None:
        if not self._provider_settings.model_id:
            raise ValueError(f"No model configured for {self._provider_label}.")
        if self._provider_id == "groq" and not self._api_key:
            raise ValueError("Groq API key is not configured. Set GROQ_API_KEY or save a local provider API key.")
        self.list_models()
        self._runtime_summary = describe_refinement_runtime(self._settings)

    def unload(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_runtime_summary(self) -> dict[str, object]:
        summary = dict(self._runtime_summary)
        if self._last_usage:
            summary["last_usage"] = dict(self._last_usage)
        if self._last_rate_limit:
            summary["rate_limit"] = dict(self._last_rate_limit)
        return summary

    def list_models(self) -> list[dict[str, object]]:
        self._require_api_key_if_needed()
        response = self._request("GET", "models")
        data = response.json().get("data", [])
        if not isinstance(data, list):
            raise RuntimeError(f"{self._provider_label} returned an invalid model list.")
        models: list[dict[str, object]] = []
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                models.append({"id": item["id"], "object": item.get("object", "model")})
        return models

    def refine(
        self,
        text: str,
        *,
        instructions: str = "",
        temperature: float,
        top_p: float,
        top_k: int,
        repetition_penalty: float,
        use_thinking: bool,
        allow_skip: bool = True,
    ) -> GenerationResult:
        if not text or not text.strip():
            return GenerationResult(content=text)

        from src.refinement.skip_check import should_skip_refinement

        if allow_skip:
            skip_reason = should_skip_refinement(text)
            if skip_reason:
                logger.debug("Skipping external refinement (%s): %r", skip_reason, text[:80])
                return GenerationResult(content=text)

        capabilities = self._capabilities()
        prompt_builder = PromptBuilder(
            system_prompt=self._settings.refinement.system_prompt,
            invariants=self._settings.refinement.invariants,
        )
        messages = prompt_builder.build_refinement_messages(
            text,
            instructions,
            use_thinking=use_thinking,
            thinking_directive=capabilities.thinking_directive(use_thinking=use_thinking),
        )
        result = self._chat_completion(
            capabilities=capabilities,
            messages=messages,
            max_tokens=self._refinement_max_tokens(text, use_thinking=use_thinking),
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=repetition_penalty,
            use_thinking=use_thinking,
        )
        if not result.content.strip():
            detail = " after producing reasoning only" if result.reasoning else ""
            raise ProviderRequestError(
                f"{self._provider_label} returned empty refinement output{detail}. "
                "Disable thinking for this model or increase the provider max output tokens.",
                status_code=502,
            )
        return result

    def generate_custom(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 150,
        temperature: float = 0.7,
        use_thinking: bool = False,
    ) -> GenerationResult:
        capabilities = self._capabilities()
        prompt_builder = PromptBuilder()
        messages = prompt_builder.build_custom_messages(
            system_prompt,
            user_prompt,
            use_thinking=use_thinking,
            thinking_directive=capabilities.thinking_directive(use_thinking=use_thinking),
        )
        return self._chat_completion(
            capabilities=capabilities,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=1.0,
            top_k=0,
            repetition_penalty=1.0,
            use_thinking=use_thinking,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _capabilities(self) -> ProviderCapabilities:
        return resolve_capabilities(self._provider_id, self._provider_settings.model_id)

    @property
    def _provider_label(self) -> str:
        return "LM Studio" if self._provider_id == "lm_studio" else "Groq"

    @property
    def _api_key(self) -> str | None:
        return (
            normalize_provider_api_key(self._provider_id, self._provider_settings.api_key)
            or get_provider_api_key(self._provider_id)
            or api_key_from_env(self._provider_id, self._provider_settings.api_key_env)
        )

    def _require_api_key_if_needed(self) -> None:
        if self._provider_id == "groq":
            try:
                validate_provider_api_key(self._provider_id, self._api_key)
            except ValueError as exc:
                if not self._api_key:
                    raise ValueError(
                        "Groq API key is not configured. Set GROQ_API_KEY or save a local provider API key."
                    ) from exc
                raise

    @property
    def _client_instance(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client()
        return self._client

    def _request_timeout(self, endpoint: str, *, json_payload: dict[str, object] | None = None) -> httpx.Timeout:
        read_timeout = max(1.0, float(self._provider_settings.timeout_seconds))
        if endpoint == "chat/completions":
            read_timeout = self._chat_completion_read_timeout(read_timeout, json_payload)
        return httpx.Timeout(
            connect=self._CONNECT_TIMEOUT_SECONDS,
            read=read_timeout,
            write=self._WRITE_TIMEOUT_SECONDS,
            pool=self._POOL_TIMEOUT_SECONDS,
        )

    def _chat_completion_read_timeout(
        self,
        baseline_timeout: float,
        json_payload: dict[str, object] | None,
    ) -> float:
        if self._provider_id != "lm_studio" or not isinstance(json_payload, dict):
            return baseline_timeout

        messages = json_payload.get("messages")
        if not isinstance(messages, list):
            return baseline_timeout

        prompt_words = sum(
            len(str(message.get("content", "")).split()) for message in messages if isinstance(message, dict)
        )
        requested_tokens = self._requested_completion_tokens(json_payload)

        if (
            prompt_words < self._LM_STUDIO_LONG_PROMPT_WORD_THRESHOLD
            and requested_tokens <= self._LM_STUDIO_LONG_COMPLETION_TOKEN_THRESHOLD
        ):
            return baseline_timeout

        estimated_output_tokens = max(512, prompt_words * 2)
        if requested_tokens > 0:
            estimated_output_tokens = min(requested_tokens, estimated_output_tokens)

        estimated_timeout = max(
            baseline_timeout,
            15.0
            + (prompt_words / self._LM_STUDIO_PROMPT_WORDS_PER_SECOND)
            + (estimated_output_tokens / self._LM_STUDIO_GENERATION_TOKENS_PER_SECOND),
        )
        scaled_timeout = min(self._LM_STUDIO_MAX_READ_TIMEOUT_SECONDS, estimated_timeout)
        if scaled_timeout > baseline_timeout:
            logger.debug(
                "LM Studio read timeout scaled from %.1fs to %.1fs (prompt_words=%d, requested_tokens=%d)",
                baseline_timeout,
                scaled_timeout,
                prompt_words,
                requested_tokens,
            )
        return scaled_timeout

    @staticmethod
    def _requested_completion_tokens(json_payload: dict[str, object]) -> int:
        raw_value = json_payload.get("max_tokens", json_payload.get("max_completion_tokens", 0))
        try:
            return max(0, int(raw_value))
        except (TypeError, ValueError):
            return 0

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = self._api_key
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _url(self, endpoint: str) -> str:
        base_url = self._provider_settings.base_url.rstrip("/")
        return f"{base_url}/{endpoint.lstrip('/')}"

    def _request(self, method: str, endpoint: str, *, json_payload: dict[str, object] | None = None) -> httpx.Response:
        self._require_api_key_if_needed()
        attempts = max(1, self._max_retries + 1)
        last_error: Exception | None = None
        timeout = self._request_timeout(endpoint, json_payload=json_payload)
        for attempt in range(attempts):
            try:
                response = self._client_instance.request(
                    method,
                    self._url(endpoint),
                    headers=self._headers(),
                    json=json_payload,
                    timeout=timeout,
                )
                self._capture_rate_limits(response)
                if response.status_code < 400:
                    return response
                if attempt < attempts - 1 and self._should_retry(response.status_code):
                    time.sleep(self._retry_delay(response))
                    continue
                raise ProviderRequestError(self._error_message(response), status_code=response.status_code)
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(self._retry_delay(None))
                    continue
                raise ProviderRequestError(
                    f"{self._provider_label} did not respond within {timeout.read:g}s at "
                    f"{self._provider_settings.base_url}. The server may be busy or stalled.",
                    status_code=504,
                ) from exc
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(self._retry_delay(None))
                    continue
                raise ProviderRequestError(
                    f"{self._provider_label} is unreachable at {self._provider_settings.base_url}: {exc}",
                    status_code=503,
                ) from exc
        raise ProviderRequestError(str(last_error) if last_error else f"{self._provider_label} request failed")

    @property
    def _max_retries(self) -> int:
        if self._provider_id != "groq":
            return 0
        return max(0, int(getattr(self._provider_settings, "max_retries", 0)))

    def _should_retry(self, status_code: int) -> bool:
        return self._provider_id == "groq" and status_code in {429, 498, 500, 502, 503}

    def _retry_delay(self, response: httpx.Response | None) -> float:
        if response is not None:
            raw = response.headers.get("retry-after")
            if raw:
                try:
                    return max(0.0, float(raw))
                except ValueError:
                    pass
        return max(0.0, float(getattr(self._provider_settings, "retry_backoff_seconds", 1.0)))

    def _error_message(self, response: httpx.Response) -> str:
        provider = self._provider_label
        detail = response.text
        try:
            body = response.json()
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                detail = error["message"]
            elif isinstance(body, dict) and isinstance(body.get("message"), str):
                detail = body["message"]
        except ValueError:
            pass

        match response.status_code:
            case 401:
                return f"{provider} authentication failed. Check the configured API key source in Settings."
            case 403:
                return f"{provider} rejected the request. Check API key permissions and model access."
            case 404:
                return f"{provider} endpoint or model was not found. Check base URL and model id."
            case 413:
                return (
                    f"{provider} rejected the request because it is too large. "
                    "Reduce transcript size or output token limit."
                )
            case 422:
                return f"{provider} could not process the request: {detail}"
            case 429:
                retry_after = response.headers.get("retry-after")
                suffix = f" Retry after {retry_after}s." if retry_after else ""
                return f"{provider} rate limit exceeded.{suffix}"
            case 498:
                return f"{provider} capacity is temporarily exhausted. Try again later."
            case 500 | 502 | 503:
                return f"{provider} is temporarily unavailable: {detail}"
            case _:
                return f"{provider} request failed with HTTP {response.status_code}: {detail}"

    def _chat_completion(
        self,
        *,
        capabilities: ProviderCapabilities,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        repetition_penalty: float,
        use_thinking: bool = False,
    ) -> GenerationResult:
        force_text_schema = capabilities.force_text_schema
        request_tokens = max(1, max_tokens)
        if force_text_schema:
            request_tokens = max(request_tokens, capabilities.schema_min_output_tokens)

        chat_template_kwargs = capabilities.chat_template_kwargs(use_thinking=use_thinking)
        reasoning_effort = capabilities.reasoning_effort_value(use_thinking=use_thinking)

        while True:
            payload = self._build_chat_payload(
                messages=messages,
                request_tokens=request_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repetition_penalty=repetition_penalty,
                force_text_schema=force_text_schema,
                chat_template_kwargs=chat_template_kwargs,
                reasoning_effort=reasoning_effort,
            )

            try:
                response = self._request("POST", "chat/completions", json_payload=payload)
                break
            except ProviderRequestError as exc:
                next_tokens = self._smaller_retry_budget(request_tokens, exc)
                if next_tokens is None:
                    raise
                logger.warning(
                    "%s rejected completion budget %d (HTTP %d). Retrying with %d.",
                    self._provider_label,
                    request_tokens,
                    exc.status_code,
                    next_tokens,
                )
                request_tokens = next_tokens

        return self._parse_chat_response(response.json())

    def _build_chat_payload(
        self,
        *,
        messages: list[dict[str, str]],
        request_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
        repetition_penalty: float,
        force_text_schema: bool,
        chat_template_kwargs: dict[str, object] | None,
        reasoning_effort: str | None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self._provider_settings.model_id,
            "messages": messages,
            "temperature": max(0.01, temperature),
            "top_p": top_p,
            "stream": False,
        }
        if self._provider_id == "groq":
            payload["max_completion_tokens"] = request_tokens
            payload["reasoning_format"] = "parsed"
            if reasoning_effort is not None:
                payload["reasoning_effort"] = reasoning_effort
        else:
            payload["max_tokens"] = request_tokens
            if top_k > 0:
                payload["top_k"] = top_k
            if repetition_penalty != 1.0:
                payload["repeat_penalty"] = repetition_penalty
            if force_text_schema:
                payload["response_format"] = TEXT_RESPONSE_FORMAT
            if chat_template_kwargs is not None:
                payload["chat_template_kwargs"] = chat_template_kwargs
            if reasoning_effort is not None:
                payload["reasoning_effort"] = reasoning_effort
        return payload

    def _parse_chat_response(self, body: dict[str, object]) -> GenerationResult:
        self._last_usage = body.get("usage") if isinstance(body.get("usage"), dict) else None
        try:
            choice = body["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"{self._provider_label} returned an invalid chat completion response.") from exc
        if not isinstance(message, dict):
            raise RuntimeError(f"{self._provider_label} returned an invalid chat completion message.")

        content = message.get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            raise RuntimeError(f"{self._provider_label} returned non-text chat completion content.")
        prompt_tokens, completion_tokens, total_tokens = self._usage_counts()
        reasoning = self._message_reasoning(message)
        schema_text = self._text_from_schema_output(content) or self._text_from_schema_output(reasoning or "")
        if schema_text is not None:
            return GenerationResult(
                content=schema_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )

        parsed = parse_generation_output(content)
        combined_reasoning = "\n\n".join(part for part in (parsed.reasoning, reasoning) if part) or None
        if combined_reasoning and not parsed.content.strip():
            logger.warning(
                "%s returned reasoning-only chat completion (finish_reason=%s).",
                self._provider_label,
                choice.get("finish_reason"),
            )
        return GenerationResult(
            content=parsed.content,
            reasoning=combined_reasoning,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def _smaller_retry_budget(self, current_tokens: int, exc: ProviderRequestError) -> int | None:
        if exc.status_code != 413:
            return None
        if current_tokens <= 128:
            return None
        return max(128, current_tokens // 2)

    @staticmethod
    def _text_from_schema_output(text: str) -> str | None:
        if not text or not text.strip():
            return None
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```").removesuffix("```").strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict) and isinstance(parsed.get("text"), str):
            return parsed["text"].strip()
        return None

    @staticmethod
    def _message_reasoning(message: dict[str, object]) -> str | None:
        from src.refinement.providers.capabilities import REASONING_MESSAGE_FIELDS

        for field in REASONING_MESSAGE_FIELDS:
            value = message.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _usage_counts(self) -> tuple[int, int, int]:
        usage = self._last_usage or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        return prompt_tokens, completion_tokens, total_tokens

    def _refinement_max_tokens(self, text: str, *, use_thinking: bool = False) -> int:
        words = max(1, len(text.split()))
        heuristic = max(256, int(words * 1.75) + 128)
        if use_thinking:
            heuristic += RefinementEngine.THINKING_BUDGET_TOKENS
        return min(max(1, self._provider_settings.max_output_tokens), heuristic)

    def _capture_rate_limits(self, response: httpx.Response) -> None:
        keys = (
            "retry-after",
            "x-ratelimit-limit-requests",
            "x-ratelimit-limit-tokens",
            "x-ratelimit-remaining-requests",
            "x-ratelimit-remaining-tokens",
            "x-ratelimit-reset-requests",
            "x-ratelimit-reset-tokens",
        )
        self._last_rate_limit = {key: response.headers[key] for key in keys if key in response.headers}


__all__ = ["OpenAICompatibleRefinementProvider"]
