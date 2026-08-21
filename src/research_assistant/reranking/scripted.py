"""Score-map reranker for unit tests. Never used as a production default."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from research_assistant.core.timing import Timer
from research_assistant.reranking.identity import RerankerIdentity
from research_assistant.reranking.models import RerankResult
from research_assistant.reranking.ranking import empty_result, ranked_result, require_query, require_top_k
from research_assistant.retrieval.models import RetrievalHit


class ScriptedReranker:
    """Assigns predetermined scores by ``chunk_id``. Missing ids score 0.0."""

    def __init__(self, scores: Mapping[str, float] | None = None) -> None:
        self._scores = dict(scores or {})
        self._identity = RerankerIdentity(
            provider="scripted",
            model_name="scripted.v1",
            revision="1",
            max_length=0,
            batch_size=0,
            scoring="scripted",
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
        with Timer("scripted_rerank") as timer:
            scored = [(hit, float(self._scores.get(hit.chunk_id, 0.0))) for hit in candidates]
        return ranked_result(
            query,
            self._identity,
            scored,
            top_k=top_k,
            truncated_count=0,
            inference_ms=timer.seconds * 1000,
        )
