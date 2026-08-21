"""Thin evidence pipeline: hybrid retrieval → rerank → context. Stages stay independent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.context.models import ContextBundle
from research_assistant.core.settings import Settings, load_settings
from research_assistant.core.types import RetrievalMode
from research_assistant.reranking.models import RerankResult
from research_assistant.reranking.service import RerankingService
from research_assistant.retrieval.filters import RetrievalFilter
from research_assistant.retrieval.hybrid import HybridSearchResult, HybridSearchService


@dataclass(frozen=True)
class EvidenceResult:
    query: str
    search: HybridSearchResult
    rerank: RerankResult
    context: ContextBundle

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "search": {
                "mode": self.search.mode,
                "hits": [hit.to_dict() for hit in self.search.hits],
                "diagnostics": self.search.diagnostics.to_dict(),
            },
            "rerank": {
                "hits": [hit.to_dict() for hit in self.rerank.hits],
                "diagnostics": self.rerank.diagnostics.to_dict(),
            },
            "context": self.context.to_dict(),
        }


class EvidencePipeline:
    """Compose first-stage retrieval, second-stage rerank, and context building."""

    def __init__(
        self,
        *,
        hybrid: HybridSearchService,
        reranker: RerankingService,
        context: CitationAwareContextBuilder,
        settings: Settings | None = None,
    ) -> None:
        self._hybrid = hybrid
        self._reranker = reranker
        self._context = context
        self._settings = settings or load_settings()

    def collect(
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
    ) -> EvidenceResult:
        pool_k = candidate_k if candidate_k is not None else self._settings.rerank_candidate_k
        search = self._hybrid.search(
            query,
            chunker_id=chunker_id,
            mode=mode,
            top_k=pool_k,
            filters=filters,
        )
        rerank = self._reranker.rerank(
            query,
            search.hits,
            top_k=rerank_top_k,
            enabled=rerank_enabled,
        )
        bundle = self._context.build(
            rerank.hits,
            query=query,
            max_tokens=max_context_tokens,
        )
        return EvidenceResult(
            query=query,
            search=search,
            rerank=rerank,
            context=bundle,
        )
