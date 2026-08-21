"""Deterministic token-overlap reranker. Tests and CI; not a production ranker."""

from __future__ import annotations

from collections.abc import Sequence

from research_assistant.core.timing import Timer
from research_assistant.reranking.identity import RerankerIdentity
from research_assistant.reranking.models import RerankResult
from research_assistant.reranking.ranking import empty_result, ranked_result, require_query, require_top_k
from research_assistant.reranking.truncate import prepare_rerank_pair
from research_assistant.retrieval.models import RetrievalHit
from research_assistant.retrieval.tokenize import tokenize


class OverlapReranker:
    """Score = query-token overlap in the candidate, plus an exact-phrase bonus."""

    def __init__(self, *, max_length: int = 0) -> None:
        self._identity = RerankerIdentity(
            provider="overlap",
            model_name="overlap.v1",
            revision="1",
            max_length=max_length,
            batch_size=0,
            scoring="token_overlap",
            device="cpu",
        )

    @property
    def identity(self) -> RerankerIdentity:
        return self._identity

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalHit],
        top_k: int,
    ) -> RerankResult:
        query = require_query(query)
        top_k = require_top_k(top_k)
        if not candidates:
            return empty_result(query, self._identity, enabled=True)
        truncated_count = 0
        scored: list[tuple[RetrievalHit, float]] = []
        with Timer("overlap_rerank") as timer:
            for hit in candidates:
                _q, passage, truncated = prepare_rerank_pair(
                    query, hit.text, self._identity.max_length
                )
                if truncated:
                    truncated_count += 1
                scored.append((hit, _overlap_score(query, passage)))
        return ranked_result(
            query,
            self._identity,
            scored,
            top_k=top_k,
            truncated_count=truncated_count,
            inference_ms=timer.seconds * 1000,
        )


def _overlap_score(query: str, text: str) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0
    text_tokens = set(tokenize(text))
    overlap = sum(1.0 for token in query_tokens if token in text_tokens)
    if query.lower() in text.lower():
        overlap += 5.0
    return overlap
