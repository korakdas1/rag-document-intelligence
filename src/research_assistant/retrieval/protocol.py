"""Swappable retrieval-stage protocols. No Qdrant or LLM types."""

from __future__ import annotations

from typing import Protocol

from research_assistant.retrieval.filters import RetrievalFilter
from research_assistant.retrieval.lexical import LexicalSearchResult


class KeywordRetriever(Protocol):
    def search(
        self,
        query: str,
        *,
        chunker_id: str,
        top_k: int | None = None,
        filters: RetrievalFilter | None = None,
    ) -> LexicalSearchResult: ...
