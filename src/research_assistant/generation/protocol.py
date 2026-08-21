"""LLMClient protocol. Implementations must not retrieve, rerank, or read SQLite."""

from __future__ import annotations

from typing import Protocol

from research_assistant.generation.identity import LLMIdentity
from research_assistant.generation.models import LLMRequest, LLMResponse


class LLMClient(Protocol):
    @property
    def identity(self) -> LLMIdentity: ...

    def generate(self, request: LLMRequest) -> LLMResponse: ...
