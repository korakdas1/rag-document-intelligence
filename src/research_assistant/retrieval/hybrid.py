"""Hybrid retrieval: dense + lexical + fusion. No rerank, no LLM."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from research_assistant.core.errors import RetrievalError
from research_assistant.core.logging import get_logger
from research_assistant.core.settings import Settings, load_settings
from research_assistant.core.timing import Timer
from research_assistant.core.types import RetrievalMode
from research_assistant.retrieval.dense import DenseSearchService
from research_assistant.retrieval.filters import RetrievalFilter
from research_assistant.retrieval.fusion import (
    FusionStrategy,
    RankedItem,
    ReciprocalRankFusion,
)
from research_assistant.retrieval.lexical import LexicalRetriever
from research_assistant.retrieval.models import RetrievalHit

logger = get_logger("research_assistant.retrieval.hybrid")


@dataclass(frozen=True)
class RetrievalDiagnostics:
    mode: str
    chunker_id: str
    dense_index_id: str | None
    lexical_index_id: str | None
    dense_candidate_k: int
    lexical_candidate_k: int
    final_top_k: int
    rrf_k: int
    dense_hit_count: int
    lexical_hit_count: int
    dense_ms: float
    lexical_ms: float
    fusion_ms: float
    total_ms: float
    filters: dict[str, Any]
    fusion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "chunker_id": self.chunker_id,
            "dense_index_id": self.dense_index_id,
            "lexical_index_id": self.lexical_index_id,
            "dense_candidate_k": self.dense_candidate_k,
            "lexical_candidate_k": self.lexical_candidate_k,
            "final_top_k": self.final_top_k,
            "rrf_k": self.rrf_k,
            "dense_hit_count": self.dense_hit_count,
            "lexical_hit_count": self.lexical_hit_count,
            "dense_ms": round(self.dense_ms, 2),
            "lexical_ms": round(self.lexical_ms, 2),
            "fusion_ms": round(self.fusion_ms, 2),
            "total_ms": round(self.total_ms, 2),
            "filters": self.filters,
            "fusion": self.fusion,
        }


@dataclass(frozen=True)
class HybridSearchResult:
    query: str
    mode: str
    hits: tuple[RetrievalHit, ...]
    diagnostics: RetrievalDiagnostics

    @property
    def search_ms(self) -> float:
        return self.diagnostics.total_ms


class HybridSearchService:
    """Orchestrates dense, lexical, or hybrid retrieval. No hidden fallback."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        dense: DenseSearchService | None = None,
        lexical: LexicalRetriever | None = None,
        fusion: FusionStrategy | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._dense = dense or DenseSearchService(settings=self._settings)
        self._lexical = lexical or LexicalRetriever(settings=self._settings)
        self._fusion = fusion or ReciprocalRankFusion(k=self._settings.rrf_k)

    def search(
        self,
        query: str,
        *,
        chunker_id: str,
        mode: str = RetrievalMode.HYBRID.value,
        top_k: int | None = None,
        filters: RetrievalFilter | None = None,
        dense_candidate_k: int | None = None,
        lexical_candidate_k: int | None = None,
    ) -> HybridSearchResult:
        if not query or not query.strip():
            raise RetrievalError("Query text is empty", code="empty_query")
        try:
            resolved_mode = RetrievalMode(mode)
        except ValueError as exc:
            raise RetrievalError(
                f"Unsupported retrieval mode {mode!r}",
                code="unsupported_mode",
            ) from exc
        final_k = top_k if top_k is not None else self._settings.default_top_k
        if final_k < 1:
            raise RetrievalError("top_k must be >= 1", code="invalid_top_k")
        dense_k = dense_candidate_k or self._settings.dense_candidate_k
        lexical_k = lexical_candidate_k or self._settings.lexical_candidate_k
        if dense_k < 1 or lexical_k < 1:
            raise RetrievalError(
                "candidate depths must be >= 1",
                code="invalid_top_k",
            )
        filter_payload = filters.to_dict() if filters is not None else {}
        started = time.perf_counter()
        if resolved_mode is RetrievalMode.DENSE:
            result = self._dense_only(
                query.strip(),
                chunker_id=chunker_id,
                top_k=final_k,
                filters=filters,
                filter_payload=filter_payload,
            )
        elif resolved_mode is RetrievalMode.LEXICAL:
            result = self._lexical_only(
                query.strip(),
                chunker_id=chunker_id,
                top_k=final_k,
                filters=filters,
                filter_payload=filter_payload,
            )
        else:
            result = self._hybrid(
                query.strip(),
                chunker_id=chunker_id,
                final_k=final_k,
                dense_k=dense_k,
                lexical_k=lexical_k,
                filters=filters,
                filter_payload=filter_payload,
            )
        total_ms = (time.perf_counter() - started) * 1000
        diagnostics = result.diagnostics
        filled = RetrievalDiagnostics(
            mode=diagnostics.mode,
            chunker_id=diagnostics.chunker_id,
            dense_index_id=diagnostics.dense_index_id,
            lexical_index_id=diagnostics.lexical_index_id,
            dense_candidate_k=diagnostics.dense_candidate_k,
            lexical_candidate_k=diagnostics.lexical_candidate_k,
            final_top_k=diagnostics.final_top_k,
            rrf_k=diagnostics.rrf_k,
            dense_hit_count=diagnostics.dense_hit_count,
            lexical_hit_count=diagnostics.lexical_hit_count,
            dense_ms=diagnostics.dense_ms,
            lexical_ms=diagnostics.lexical_ms,
            fusion_ms=diagnostics.fusion_ms,
            total_ms=total_ms,
            filters=diagnostics.filters,
            fusion=diagnostics.fusion,
        )
        return HybridSearchResult(
            query=result.query,
            mode=result.mode,
            hits=result.hits,
            diagnostics=filled,
        )

    def _dense_only(
        self,
        query: str,
        *,
        chunker_id: str,
        top_k: int,
        filters: RetrievalFilter | None,
        filter_payload: dict[str, Any],
    ) -> HybridSearchResult:
        result = self._dense.search(
            query, chunker_id=chunker_id, top_k=top_k, filters=filters
        )
        diagnostics = RetrievalDiagnostics(
            mode=RetrievalMode.DENSE.value,
            chunker_id=chunker_id,
            dense_index_id=result.index_id,
            lexical_index_id=None,
            dense_candidate_k=top_k,
            lexical_candidate_k=0,
            final_top_k=top_k,
            rrf_k=self._settings.rrf_k,
            dense_hit_count=len(result.hits),
            lexical_hit_count=0,
            dense_ms=result.search_ms,
            lexical_ms=0.0,
            fusion_ms=0.0,
            total_ms=result.search_ms,
            filters=filter_payload,
            fusion="none",
        )
        return HybridSearchResult(
            query=query,
            mode=RetrievalMode.DENSE.value,
            hits=result.hits,
            diagnostics=diagnostics,
        )

    def _lexical_only(
        self,
        query: str,
        *,
        chunker_id: str,
        top_k: int,
        filters: RetrievalFilter | None,
        filter_payload: dict[str, Any],
    ) -> HybridSearchResult:
        result = self._lexical.search(
            query, chunker_id=chunker_id, top_k=top_k, filters=filters
        )
        diagnostics = RetrievalDiagnostics(
            mode=RetrievalMode.LEXICAL.value,
            chunker_id=chunker_id,
            dense_index_id=None,
            lexical_index_id=result.lexical_index_id,
            dense_candidate_k=0,
            lexical_candidate_k=top_k,
            final_top_k=top_k,
            rrf_k=self._settings.rrf_k,
            dense_hit_count=0,
            lexical_hit_count=len(result.hits),
            dense_ms=0.0,
            lexical_ms=result.search_ms,
            fusion_ms=0.0,
            total_ms=result.search_ms,
            filters=filter_payload,
            fusion="none",
        )
        return HybridSearchResult(
            query=query,
            mode=RetrievalMode.LEXICAL.value,
            hits=result.hits,
            diagnostics=diagnostics,
        )

    def _hybrid(
        self,
        query: str,
        *,
        chunker_id: str,
        final_k: int,
        dense_k: int,
        lexical_k: int,
        filters: RetrievalFilter | None,
        filter_payload: dict[str, Any],
    ) -> HybridSearchResult:
        dense = self._dense.search(
            query, chunker_id=chunker_id, top_k=dense_k, filters=filters
        )
        lexical = self._lexical.search(
            query, chunker_id=chunker_id, top_k=lexical_k, filters=filters
        )
        with Timer("fusion") as fusion_timer:
            fused = self._fusion.fuse(
                [
                    [
                        RankedItem(
                            chunk_id=hit.chunk_id,
                            rank=hit.rank,
                            score=hit.score,
                            retriever="dense",
                        )
                        for hit in dense.hits
                    ],
                    [
                        RankedItem(
                            chunk_id=hit.chunk_id,
                            rank=hit.rank,
                            score=hit.score,
                            retriever="lexical",
                        )
                        for hit in lexical.hits
                    ],
                ]
            )
            catalog: dict[str, RetrievalHit] = {}
            dense_by_id = {hit.chunk_id: hit for hit in dense.hits}
            lexical_by_id = {hit.chunk_id: hit for hit in lexical.hits}
            catalog.update(lexical_by_id)
            catalog.update(dense_by_id)
            hits: list[RetrievalHit] = []
            for rank, item in enumerate(fused[:final_k], start=1):
                base = catalog[item.chunk_id]
                dense_hit = dense_by_id.get(item.chunk_id)
                hits.append(
                    RetrievalHit(
                        chunk_id=base.chunk_id,
                        document_id=base.document_id,
                        rank=rank,
                        score=item.fused_score,
                        retriever="hybrid",
                        text=base.text,
                        page_start=base.page_start,
                        page_end=base.page_end,
                        section_path=base.section_path,
                        chunker_id=base.chunker_id,
                        index_id=dense.index_id,
                        embedding_model_id=(
                            dense_hit.embedding_model_id if dense_hit else ""
                        ),
                        filename=base.filename,
                        content_hash=base.content_hash,
                        retrievers=tuple(sorted(item.ranks)),
                        dense_rank=item.ranks.get("dense"),
                        lexical_rank=item.ranks.get("lexical"),
                        dense_score=item.scores.get("dense"),
                        lexical_score=item.scores.get("lexical"),
                        fused_score=item.fused_score,
                        lexical_index_id=lexical.lexical_index_id,
                    )
                )
        diagnostics = RetrievalDiagnostics(
            mode=RetrievalMode.HYBRID.value,
            chunker_id=chunker_id,
            dense_index_id=dense.index_id,
            lexical_index_id=lexical.lexical_index_id,
            dense_candidate_k=dense_k,
            lexical_candidate_k=lexical_k,
            final_top_k=final_k,
            rrf_k=self._settings.rrf_k,
            dense_hit_count=len(dense.hits),
            lexical_hit_count=len(lexical.hits),
            dense_ms=dense.search_ms,
            lexical_ms=lexical.search_ms,
            fusion_ms=fusion_timer.seconds * 1000,
            total_ms=dense.search_ms + lexical.search_ms + fusion_timer.seconds * 1000,
            filters=filter_payload,
            fusion="rrf.v1",
        )
        logger.info(
            "hybrid_search_completed hits=%s dense=%s lexical=%s total_ms=%.1f",
            len(hits),
            len(dense.hits),
            len(lexical.hits),
            diagnostics.total_ms,
        )
        return HybridSearchResult(
            query=query,
            mode=RetrievalMode.HYBRID.value,
            hits=tuple(hits),
            diagnostics=diagnostics,
        )
