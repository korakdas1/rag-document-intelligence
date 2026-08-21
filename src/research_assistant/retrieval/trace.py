"""Developer retrieval tracing for one target chunk. No embeddings are exposed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.core.settings import Settings, load_settings
from research_assistant.reranking.service import RerankingService
from research_assistant.retrieval.dense import DenseSearchService
from research_assistant.retrieval.filters import RetrievalFilter
from research_assistant.retrieval.hybrid import HybridSearchService
from research_assistant.retrieval.lexical import LexicalRetriever
from research_assistant.retrieval.models import RetrievalHit


@dataclass(frozen=True)
class RetrievalTrace:
    query: str
    target_chunk_id: str
    chunker_id: str
    rerank_enabled: bool
    dense_rank: int | None
    dense_score: float | None
    lexical_rank: int | None
    lexical_score: float | None
    hybrid_rank: int | None
    fused_score: float | None
    rerank_rank: int | None
    rerank_score: float | None
    selected_in_context: bool
    context_position: int | None
    context_citation_id: str | None
    context_truncated: bool
    context_tokens_used_before: int | None
    context_candidate_tokens: int | None
    context_tokens_added: int | None
    context_budget: int
    dropped_reason: str | None
    dense_candidate_k: int
    lexical_candidate_k: int
    hybrid_candidate_k: int
    rerank_top_k: int
    context_chunk_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "target_chunk_id": self.target_chunk_id,
            "chunker_id": self.chunker_id,
            "rerank_enabled": self.rerank_enabled,
            "dense_rank": self.dense_rank,
            "dense_score": self.dense_score,
            "lexical_rank": self.lexical_rank,
            "lexical_score": self.lexical_score,
            "hybrid_rank": self.hybrid_rank,
            "fused_score": self.fused_score,
            "rerank_rank": self.rerank_rank,
            "rerank_score": self.rerank_score,
            "selected_in_context": self.selected_in_context,
            "context_position": self.context_position,
            "context_citation_id": self.context_citation_id,
            "context_truncated": self.context_truncated,
            "context_tokens_used_before": self.context_tokens_used_before,
            "context_candidate_tokens": self.context_candidate_tokens,
            "context_tokens_added": self.context_tokens_added,
            "context_budget": self.context_budget,
            "dropped_reason": self.dropped_reason,
            "dense_candidate_k": self.dense_candidate_k,
            "lexical_candidate_k": self.lexical_candidate_k,
            "hybrid_candidate_k": self.hybrid_candidate_k,
            "rerank_top_k": self.rerank_top_k,
            "context_chunk_ids": list(self.context_chunk_ids),
        }


class RetrievalTracer:
    """Run production retrieval stages and locate one target at every cutoff."""

    def __init__(
        self,
        *,
        dense: DenseSearchService,
        lexical: LexicalRetriever,
        hybrid: HybridSearchService,
        reranker: RerankingService,
        context: CitationAwareContextBuilder,
        settings: Settings | None = None,
    ) -> None:
        self._dense = dense
        self._lexical = lexical
        self._hybrid = hybrid
        self._reranker = reranker
        self._context = context
        self._settings = settings or load_settings()

    def trace(
        self,
        query: str,
        *,
        target_chunk_id: str,
        chunker_id: str,
        filters: RetrievalFilter | None = None,
        rerank_enabled: bool = True,
        candidate_k: int | None = None,
        rerank_top_k: int | None = None,
        max_context_tokens: int | None = None,
    ) -> RetrievalTrace:
        pool_k = candidate_k or self._settings.rerank_candidate_k
        rerank_k = rerank_top_k or self._settings.rerank_top_k
        dense_k = self._settings.dense_candidate_k
        lexical_k = self._settings.lexical_candidate_k
        budget = max_context_tokens or self._settings.max_context_tokens

        dense = self._dense.search(
            query,
            chunker_id=chunker_id,
            top_k=dense_k,
            filters=filters,
        )
        lexical = self._lexical.search(
            query,
            chunker_id=chunker_id,
            top_k=lexical_k,
            filters=filters,
        )
        hybrid = self._hybrid.search(
            query,
            chunker_id=chunker_id,
            top_k=pool_k,
            filters=filters,
            dense_candidate_k=dense_k,
            lexical_candidate_k=lexical_k,
        )
        reranked = self._reranker.rerank(
            query,
            hybrid.hits,
            top_k=pool_k,
            enabled=rerank_enabled,
        )
        cutoff_hits = reranked.hits[:rerank_k]
        bundle = self._context.build(
            cutoff_hits,
            query=query,
            max_tokens=budget,
        )

        dense_hit = _find(dense.hits, target_chunk_id)
        lexical_hit = _find(lexical.hits, target_chunk_id)
        hybrid_hit = _find(hybrid.hits, target_chunk_id)
        rerank_hit = _find(reranked.hits, target_chunk_id)
        rerank_rank = _stage_rank(reranked.hits, target_chunk_id)
        context_item = next(
            (
                item
                for item in bundle.items
                if item.source.chunk_id == target_chunk_id
            ),
            None,
        )
        decision = next(
            (
                item
                for item in bundle.diagnostics.selection_decisions
                if item.chunk_id == target_chunk_id
            ),
            None,
        )
        dropped_reason = _dropped_reason(
            dense_hit=dense_hit,
            lexical_hit=lexical_hit,
            hybrid_hit=hybrid_hit,
            rerank_rank=rerank_rank,
            rerank_top_k=rerank_k,
            rerank_enabled=rerank_enabled,
            selected=context_item is not None,
            context_reason=decision.reason if decision else None,
        )
        return RetrievalTrace(
            query=query.strip(),
            target_chunk_id=target_chunk_id,
            chunker_id=chunker_id,
            rerank_enabled=rerank_enabled,
            dense_rank=dense_hit.rank if dense_hit else None,
            dense_score=dense_hit.score if dense_hit else None,
            lexical_rank=lexical_hit.rank if lexical_hit else None,
            lexical_score=lexical_hit.score if lexical_hit else None,
            hybrid_rank=hybrid_hit.rank if hybrid_hit else None,
            fused_score=hybrid_hit.fused_score if hybrid_hit else None,
            rerank_rank=rerank_rank,
            rerank_score=rerank_hit.rerank_score if rerank_hit else None,
            selected_in_context=context_item is not None,
            context_position=context_item.rank if context_item else None,
            context_citation_id=(
                context_item.citation_id if context_item else None
            ),
            context_truncated=(
                context_item.truncated if context_item else False
            ),
            context_tokens_used_before=(
                decision.tokens_used_before if decision else None
            ),
            context_candidate_tokens=(
                decision.candidate_tokens if decision else None
            ),
            context_tokens_added=(
                decision.tokens_added if decision else None
            ),
            context_budget=budget,
            dropped_reason=dropped_reason,
            dense_candidate_k=dense_k,
            lexical_candidate_k=lexical_k,
            hybrid_candidate_k=pool_k,
            rerank_top_k=rerank_k,
            context_chunk_ids=tuple(
                item.source.chunk_id for item in bundle.items
            ),
        )


def _find(
    hits: tuple[RetrievalHit, ...], chunk_id: str
) -> RetrievalHit | None:
    return next((item for item in hits if item.chunk_id == chunk_id), None)


def _stage_rank(
    hits: tuple[RetrievalHit, ...], chunk_id: str
) -> int | None:
    for rank, hit in enumerate(hits, start=1):
        if hit.chunk_id == chunk_id:
            return hit.rerank_rank or rank
    return None


def _dropped_reason(
    *,
    dense_hit: RetrievalHit | None,
    lexical_hit: RetrievalHit | None,
    hybrid_hit: RetrievalHit | None,
    rerank_rank: int | None,
    rerank_top_k: int,
    rerank_enabled: bool,
    selected: bool,
    context_reason: str | None,
) -> str | None:
    if selected:
        return None
    if hybrid_hit is None:
        if dense_hit is None and lexical_hit is None:
            return "not_in_dense_or_lexical_candidates"
        return "outside_hybrid_top_k"
    if rerank_rank is None:
        return "not_in_rerank_output"
    if rerank_rank > rerank_top_k:
        return (
            "outside_rerank_top_k"
            if rerank_enabled
            else "outside_passthrough_top_k"
        )
    return context_reason or "not_selected_in_context"
