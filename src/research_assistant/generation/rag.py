"""Thin RAG orchestration: resolve follow-up → evidence → grounded generation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from research_assistant.conversation.heuristic import HeuristicQueryResolver
from research_assistant.conversation.models import ConversationTurn, QueryResolution
from research_assistant.conversation.protocol import QueryResolver
from research_assistant.core.types import RetrievalMode
from research_assistant.generation.models import GroundedAnswer
from research_assistant.generation.service import GroundedGenerationService
from research_assistant.retrieval.filters import RetrievalFilter
from research_assistant.retrieval.pipeline import EvidencePipeline, EvidenceResult


@dataclass(frozen=True)
class RAGResult:
    query: str
    original_query: str
    evidence: EvidenceResult
    answer: GroundedAnswer
    resolution: QueryResolution | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "query": self.query,
            "original_query": self.original_query,
            "answer": self.answer.to_dict(),
            "search_diagnostics": self.evidence.search.diagnostics.to_dict(),
            "rerank_diagnostics": self.evidence.rerank.diagnostics.to_dict(),
            "context_diagnostics": self.evidence.context.diagnostics.to_dict(),
            "generation_diagnostics": self.answer.diagnostics.to_dict(),
        }
        if self.resolution is not None:
            payload["query_resolution"] = self.resolution.to_dict()
        return payload


class RAGService:
    """query → QueryResolver → EvidencePipeline → GroundedGenerationService."""

    def __init__(
        self,
        *,
        evidence: EvidencePipeline,
        generation: GroundedGenerationService,
        resolver: QueryResolver | None = None,
        conversation_window: int = 4,
    ) -> None:
        self._evidence = evidence
        self._generation = generation
        self._resolver = resolver or HeuristicQueryResolver(window=conversation_window)

    def answer(
        self,
        query: str,
        *,
        chunker_id: str,
        mode: str = RetrievalMode.HYBRID.value,
        filters: RetrievalFilter | None = None,
        candidate_k: int | None = None,
        rerank_top_k: int | None = None,
        max_context_tokens: int | None = None,
        rerank_enabled: bool | None = None,
        conversation: Sequence[ConversationTurn] | None = None,
    ) -> RAGResult:
        resolution = self._resolver.resolve(query, conversation)
        retrieval_query = resolution.retrieval_query
        evidence = self._evidence.collect(
            retrieval_query,
            chunker_id=chunker_id,
            mode=mode,
            filters=filters,
            candidate_k=candidate_k,
            rerank_top_k=rerank_top_k,
            max_context_tokens=max_context_tokens,
            rerank_enabled=rerank_enabled,
        )
        grounded = self._generation.generate(
            retrieval_query,
            evidence.context,
            unresolved_referent=resolution.diagnostics.method == "unresolved_no_history",
        )
        return RAGResult(
            query=retrieval_query,
            original_query=resolution.original_question,
            evidence=evidence,
            answer=grounded,
            resolution=resolution,
        )
