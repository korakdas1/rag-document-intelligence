"""Dense top-K search. No keyword, fusion, or rerank."""

from __future__ import annotations

from dataclasses import dataclass

from research_assistant.core.errors import RetrievalError, VectorStoreError
from research_assistant.core.logging import get_logger
from research_assistant.core.settings import Settings, load_settings
from research_assistant.core.timing import Timer
from research_assistant.core.types import IndexStatus
from research_assistant.embeddings.factory import embedding_model_from_settings
from research_assistant.embeddings.protocol import EmbeddingModel
from research_assistant.indexing.identity import collection_name_for, index_id_for
from research_assistant.indexing.protocol import VectorStore
from research_assistant.indexing.qdrant_store import qdrant_store_for
from research_assistant.retrieval.filters import RetrievalFilter, chunk_matches_filter
from research_assistant.retrieval.models import RetrievalHit
from research_assistant.storage.sqlite import SqliteDocumentStore

logger = get_logger("research_assistant.retrieval")


@dataclass(frozen=True)
class DenseSearchResult:
    query: str
    index_id: str
    hits: tuple[RetrievalHit, ...]
    search_ms: float


class DenseSearchService:
    def __init__(
        self,
        settings: Settings | None = None,
        store: SqliteDocumentStore | None = None,
        embedder: EmbeddingModel | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._store = store or SqliteDocumentStore(self._settings.database_path)
        self._embedder = embedder
        self._vectors = vector_store or qdrant_store_for(self._settings.vector_index_path)

    @property
    def embedder(self) -> EmbeddingModel:
        if self._embedder is None:
            self._embedder = embedding_model_from_settings(self._settings)
        return self._embedder

    def search(
        self,
        query: str,
        *,
        chunker_id: str,
        top_k: int | None = None,
        filters: RetrievalFilter | None = None,
    ) -> DenseSearchResult:
        if not query or not query.strip():
            raise RetrievalError("Query text is empty", code="empty_query")
        k = top_k if top_k is not None else self._settings.default_top_k
        if k < 1:
            raise RetrievalError("top_k must be >= 1", code="invalid_top_k")
        identity = self.embedder.identity
        index_id = index_id_for(embedding=identity, chunker_id=chunker_id)
        collection = collection_name_for(index_id)
        meta = self._store.get_vector_index(index_id)
        if meta is None or not self._vectors.collection_exists(collection):
            raise RetrievalError(
                f"No dense index for chunker_id={chunker_id} "
                f"model={identity.embedding_model_id}",
                code="missing_index",
            )
        if meta.status is not IndexStatus.READY:
            raise RetrievalError(
                f"Index {index_id} is {meta.status.value}, not ready",
                code="index_not_ready",
            )
        with Timer("dense_search") as timer:
            vector = self.embedder.embed_query(query.strip())
            try:
                raw_hits = self._vectors.search(
                    collection, vector, top_k=k, payload_filter=filters
                )
            except VectorStoreError as exc:
                raise RetrievalError(exc.message, code=exc.code) from exc
        hits: list[RetrievalHit] = []
        rank = 1
        for raw in raw_hits:
            chunk = self._store.get_chunk(raw.chunk_id)
            if chunk is None:
                logger.info(
                    "dense_search_skipped_stale chunk_id=%s",
                    raw.chunk_id[:12],
                )
                continue
            filename = raw.payload.filename
            if not chunk_matches_filter(chunk, filters, filename=filename):
                continue
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    rank=rank,
                    score=raw.score,
                    retriever="dense",
                    text=chunk.text,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    section_path=chunk.section_path,
                    chunker_id=chunk.chunker_id,
                    index_id=index_id,
                    embedding_model_id=identity.embedding_model_id,
                    filename=filename,
                    content_hash=chunk.content_hash,
                    retrievers=("dense",),
                    dense_rank=rank,
                    dense_score=raw.score,
                )
            )
            rank += 1
        logger.info(
            "dense_search_completed index_id=%s hits=%s search_ms=%.1f",
            index_id,
            len(hits),
            timer.seconds * 1000,
        )
        return DenseSearchResult(
            query=query.strip(),
            index_id=index_id,
            hits=tuple(hits),
            search_ms=timer.seconds * 1000,
        )
