"""Deterministic fake LLM. Tests and CI; no network."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from research_assistant.core.errors import GenerationError
from research_assistant.core.timing import Timer
from research_assistant.generation.identity import LLMIdentity
from research_assistant.generation.models import LLMRequest, LLMResponse

OutputFactory = str | Sequence[str] | Callable[[LLMRequest], str]


class ScriptedLLM:
    """Returns predetermined JSON/text. Records requests for assertions."""

    def __init__(
        self,
        output: OutputFactory = '{"answer": "", "insufficient_evidence": true}',
        *,
        error: Exception | None = None,
        finish_reason: str = "stop",
        output_tokens: int | None = None,
        input_tokens: int | None = None,
        provider_request_id: str | None = None,
        identity: LLMIdentity | None = None,
        generation_ms: float | None = None,
    ) -> None:
        self._output = output
        self._error = error
        self._finish_reason = finish_reason
        self._output_tokens = output_tokens
        self._input_tokens = input_tokens
        self._provider_request_id = provider_request_id
        self._forced_generation_ms = generation_ms
        self._index = 0
        self.requests: list[LLMRequest] = []
        self._identity = identity or LLMIdentity(
            provider="scripted",
            model_name="scripted.v1",
            temperature=0.0,
            max_output_tokens=512,
            response_format="json_object",
            timeout_seconds=120.0,
            base_url="",
        )

    @property
    def identity(self) -> LLMIdentity:
        return self._identity

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        with Timer("scripted_generate") as timer:
            text = self._next_text(request)
        return LLMResponse(
            text=text,
            finish_reason=self._finish_reason,
            output_tokens=self._output_tokens,
            input_tokens=self._input_tokens,
            provider_request_id=self._provider_request_id,
            generation_ms=(
                self._forced_generation_ms
                if self._forced_generation_ms is not None
                else timer.seconds * 1000
            ),
        )

    def _next_text(self, request: LLMRequest) -> str:
        if callable(self._output):
            return self._output(request)
        if isinstance(self._output, str):
            return self._output
        if not self._output:
            raise GenerationError("ScriptedLLM has no outputs left", code="malformed_output")
        if self._index >= len(self._output):
            return self._output[-1]
        text = self._output[self._index]
        self._index += 1
        return text
