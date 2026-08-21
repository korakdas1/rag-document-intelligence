"""Reranker protocol. Implementations must not query Qdrant, BM25, or LLMs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from research_assistant.reranking.identity import RerankerIdentity
from research_assistant.reranking.models import RerankResult
from research_assistant.retrieval.models import RetrievalHit


class Reranker(Protocol):
    @property
    def identity(self) -> RerankerIdentity: ...

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalHit],
        top_k: int,
    ) -> RerankResult: ...
