"""Shared ranking helpers. Preserve first-stage provenance; add rerank fields."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from research_assistant.core.errors import RerankError
from research_assistant.reranking.identity import RerankerIdentity
from research_assistant.reranking.models import RerankDiagnostics, RerankResult
from research_assistant.retrieval.models import RetrievalHit


def require_query(query: str) -> str:
    if not query or not query.strip():
        raise RerankError("Query text is empty", code="empty_query")
    return query.strip()


def require_top_k(top_k: int) -> int:
    if top_k < 1:
        raise RerankError("top_k must be >= 1", code="invalid_top_k")
    return top_k


def attach_rerank(
    hit: RetrievalHit,
    *,
    rerank_rank: int,
    rerank_score: float,
    reranker_id: str,
) -> RetrievalHit:
    """Copy a first-stage hit and add rerank fields. ``rank`` stays first-stage."""
    return replace(
        hit,
        rerank_rank=rerank_rank,
        rerank_score=rerank_score,
        reranker_id=reranker_id,
    )


def sort_scored_hits(
    scored: Sequence[tuple[RetrievalHit, float]],
) -> list[tuple[RetrievalHit, float]]:
    """Higher score first. Ties: better (lower) first-stage rank, then chunk_id."""
    return sorted(scored, key=lambda item: (-item[1], item[0].rank, item[0].chunk_id))


def empty_result(
    query: str,
    identity: RerankerIdentity,
    *,
    enabled: bool,
) -> RerankResult:
    return RerankResult(
        query=query,
        hits=(),
        diagnostics=RerankDiagnostics(
            reranker_id=identity.reranker_id,
            enabled=enabled,
            input_count=0,
            output_count=0,
            batch_size=identity.batch_size,
            truncated_count=0,
            inference_ms=0.0,
            device=identity.device,
            scoring=identity.scoring,
        ),
    )


def ranked_result(
    query: str,
    identity: RerankerIdentity,
    scored: Sequence[tuple[RetrievalHit, float]],
    *,
    top_k: int,
    truncated_count: int,
    inference_ms: float,
    enabled: bool = True,
) -> RerankResult:
    ordered = sort_scored_hits(scored)[:top_k]
    hits = tuple(
        attach_rerank(
            hit,
            rerank_rank=rank,
            rerank_score=score,
            reranker_id=identity.reranker_id,
        )
        for rank, (hit, score) in enumerate(ordered, start=1)
    )
    return RerankResult(
        query=query,
        hits=hits,
        diagnostics=RerankDiagnostics(
            reranker_id=identity.reranker_id,
            enabled=enabled,
            input_count=len(scored),
            output_count=len(hits),
            batch_size=identity.batch_size,
            truncated_count=truncated_count,
            inference_ms=inference_ms,
            device=identity.device,
            scoring=identity.scoring,
        ),
    )
