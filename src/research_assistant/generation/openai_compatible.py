"""OpenAI-compatible Chat Completions client. Stdlib HTTP; no vendor SDK."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any

from research_assistant.core.errors import GenerationError
from research_assistant.core.timing import Timer
from research_assistant.generation.identity import LLMIdentity
from research_assistant.generation.models import LLMRequest, LLMResponse


class OpenAICompatibleClient:
    """Talks to Ollama, OpenAI, or any Chat Completions endpoint."""

    def __init__(
        self,
        *,
        model_name: str,
        base_url: str,
        api_key: str = "",
        temperature: float = 0.0,
        max_output_tokens: int = 512,
        timeout_seconds: float = 120.0,
        response_format: str = "json_object",
        keep_alive: str = "",
    ) -> None:
        if not model_name.strip():
            raise GenerationError("LLM model name is empty", code="invalid_model")
        if timeout_seconds <= 0:
            raise GenerationError("timeout_seconds must be > 0", code="invalid_timeout")
        self._api_key = api_key
        self._identity = LLMIdentity(
            provider="openai_compatible",
            model_name=model_name.strip(),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_format=response_format,
            timeout_seconds=timeout_seconds,
            base_url=base_url.rstrip("/"),
        )
        self._keep_alive = keep_alive.strip()

    @property
    def identity(self) -> LLMIdentity:
        return self._identity

    def generate(self, request: LLMRequest) -> LLMResponse:
        url = f"{self._identity.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._identity.model_name,
            "messages": [message.to_dict() for message in request.messages],
            "temperature": self._identity.temperature,
            "max_tokens": self._identity.max_output_tokens,
        }
        if self._identity.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        if self._keep_alive:
            payload["keep_alive"] = self._keep_alive
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        http_request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with Timer("llm_generate") as timer:
                with urllib.request.urlopen(
                    http_request, timeout=self._identity.timeout_seconds
                ) as response:
                    raw = response.read()
        except TimeoutError as exc:
            raise GenerationError(
                f"LLM request timed out after {self._identity.timeout_seconds}s",
                code="timeout",
            ) from exc
        except socket.timeout as exc:
            raise GenerationError(
                f"LLM request timed out after {self._identity.timeout_seconds}s",
                code="timeout",
            ) from exc
        except urllib.error.HTTPError as exc:
            raise _http_error(exc) from exc
        except urllib.error.URLError as exc:
            raise GenerationError(
                f"LLM provider unavailable: {exc.reason}",
                code="provider_unavailable",
            ) from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GenerationError(
                "LLM provider returned non-JSON",
                code="malformed_output",
            ) from exc
        text = _message_text(data)
        finish_reason = None
        choices = data.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            finish_reason = _optional_str(choices[0].get("finish_reason"))
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return LLMResponse(
            text=text,
            finish_reason=finish_reason,
            output_tokens=_optional_int(usage.get("completion_tokens")),
            input_tokens=_optional_int(usage.get("prompt_tokens")),
            provider_request_id=_optional_str(data.get("id")),
            generation_ms=timer.seconds * 1000,
        )


def _message_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GenerationError(
            "LLM provider returned no choices",
            code="malformed_output",
        )
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise GenerationError(
            "LLM provider returned no message",
            code="malformed_output",
        )
    content = message.get("content")
    if not isinstance(content, str):
        raise GenerationError(
            "LLM provider returned empty content",
            code="malformed_output",
        )
    return content


def _http_error(exc: urllib.error.HTTPError) -> GenerationError:
    status = exc.code
    try:
        exc.read(512)
    except Exception:  # noqa: BLE001
        pass
    if status in {401, 403}:
        return GenerationError(
            "LLM provider rejected credentials",
            code="invalid_api_key",
        )
    if status == 404:
        return GenerationError(
            "Configured LLM model was not found at the provider.",
            code="invalid_model",
        )
    if status == 429:
        return GenerationError("LLM provider rate-limited the request", code="rate_limit")
    if status >= 500:
        return GenerationError(
            f"LLM provider error {status}",
            code="provider_unavailable",
        )
    return GenerationError(
        f"LLM provider HTTP {status}",
        code="provider_unavailable",
    )


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
