"""Rerank retrieved candidates. Does not search Qdrant or BM25."""

from __future__ import annotations

from collections.abc import Sequence

from research_assistant.core.errors import RerankError
from research_assistant.core.logging import get_logger
from research_assistant.core.settings import Settings, load_settings
from research_assistant.reranking.factory import reranker_from_settings
from research_assistant.reranking.identity import RerankerIdentity
from research_assistant.reranking.models import RerankDiagnostics, RerankResult
from research_assistant.reranking.protocol import Reranker
from research_assistant.reranking.ranking import require_query, require_top_k
from research_assistant.retrieval.models import RetrievalHit

logger = get_logger("research_assistant.reranking")

_DISABLED_IDENTITY = RerankerIdentity(
    provider="none",
    model_name="disabled",
    revision="0",
    max_length=0,
    batch_size=0,
    scoring="none",
    device="cpu",
)


class RerankingService:
    """Second-stage ranker over ``RetrievalHit`` candidates."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        reranker: Reranker | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._reranker = reranker

    @property
    def enabled(self) -> bool:
        return self._settings.rerank_enabled

    def identity(self) -> RerankerIdentity:
        if not self._settings.rerank_enabled:
            return _DISABLED_IDENTITY
        return self._engine().identity

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalHit],
        top_k: int | None = None,
        *,
        enabled: bool | None = None,
    ) -> RerankResult:
        query = require_query(query)
        k = top_k if top_k is not None else self._settings.rerank_top_k
        k = require_top_k(k)
        use_rerank = self._settings.rerank_enabled if enabled is None else enabled
        if not use_rerank:
            return _passthrough(query, candidates, k)
        try:
            engine = self._engine()
        except RerankError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RerankError(
                f"Failed to initialize reranker: {exc}",
                code="model_unavailable",
            ) from exc
        result = engine.rerank(query, candidates, k)
        logger.info(
            "rerank_completed enabled=%s input=%s output=%s ms=%.1f",
            True,
            result.diagnostics.input_count,
            result.diagnostics.output_count,
            result.diagnostics.inference_ms,
        )
        return result

    def _engine(self) -> Reranker:
        if self._reranker is None:
            self._reranker = reranker_from_settings(self._settings)
        return self._reranker


def _passthrough(
    query: str,
    candidates: Sequence[RetrievalHit],
    top_k: int,
) -> RerankResult:
    hits = tuple(candidates[:top_k])
    return RerankResult(
        query=query,
        hits=hits,
        diagnostics=RerankDiagnostics(
            reranker_id=_DISABLED_IDENTITY.reranker_id,
            enabled=False,
            input_count=len(candidates),
            output_count=len(hits),
            batch_size=0,
            truncated_count=0,
            inference_ms=0.0,
            device="cpu",
            scoring="none",
        ),
    )
