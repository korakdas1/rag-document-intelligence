"""Lexical BM25 search over SQLite chunks. Derived artifact, not a second corpus."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from research_assistant.chunking.models import Chunk
from research_assistant.core.errors import RetrievalError
from research_assistant.core.logging import get_logger
from research_assistant.core.settings import Settings, load_settings
from research_assistant.core.timing import Timer
from research_assistant.retrieval.bm25 import BM25Index
from research_assistant.retrieval.filters import RetrievalFilter, chunk_matches_filter
from research_assistant.retrieval.identity import lexical_index_id_for
from research_assistant.retrieval.models import RetrievalHit
from research_assistant.retrieval.tokenize import TOKENIZER_ID, tokenize
from research_assistant.storage.sqlite import SqliteDocumentStore

logger = get_logger("research_assistant.retrieval.lexical")


@dataclass(frozen=True)
class LexicalSearchResult:
    query: str
    lexical_index_id: str
    chunker_id: str
    hits: tuple[RetrievalHit, ...]
    search_ms: float


class LexicalRetriever:
    """BM25 over chunks for one ``chunker_id``. Rebuilds when the chunk set changes."""

    def __init__(
        self,
        settings: Settings | None = None,
        store: SqliteDocumentStore | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._store = store or SqliteDocumentStore(self._settings.database_path)
        self._cache_key: str | None = None
        self._index: BM25Index | None = None
        self._chunks: dict[str, Chunk] = {}
        self._filenames: dict[str, str] = {}

    @property
    def tokenizer_id(self) -> str:
        return TOKENIZER_ID

    def lexical_index_id(self, chunker_id: str) -> str:
        return lexical_index_id_for(
            chunker_id=chunker_id,
            tokenizer_id=TOKENIZER_ID,
            k1=self._settings.bm25_k1,
            b=self._settings.bm25_b,
        )

    def search(
        self,
        query: str,
        *,
        chunker_id: str,
        top_k: int | None = None,
        filters: RetrievalFilter | None = None,
    ) -> LexicalSearchResult:
        if not query or not query.strip():
            raise RetrievalError("Query text is empty", code="empty_query")
        k = top_k if top_k is not None else self._settings.default_top_k
        if k < 1:
            raise RetrievalError("top_k must be >= 1", code="invalid_top_k")
        query_tokens = tokenize(query.strip())
        if not query_tokens:
            raise RetrievalError(
                "Query produced no lexical tokens",
                code="no_query_terms",
            )
        index_id = self.lexical_index_id(chunker_id)
        with Timer("lexical_search") as timer:
            index, chunks, filenames = self._index_for(chunker_id)
            if not chunks:
                raise RetrievalError(
                    f"No lexical corpus for chunker_id={chunker_id}",
                    code="missing_lexical_index",
                )
            candidates = [
                chunk
                for chunk in chunks.values()
                if chunk_matches_filter(
                    chunk,
                    filters,
                    filename=filenames.get(chunk.document_id, ""),
                )
            ]
            ranked = index.rank(
                query_tokens,
                candidate_ids=[chunk.chunk_id for chunk in candidates],
                top_k=k,
            )
            hits: list[RetrievalHit] = []
            for rank, (chunk_id, score) in enumerate(ranked, start=1):
                chunk = chunks[chunk_id]
                hits.append(
                    RetrievalHit(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        rank=rank,
                        score=score,
                        retriever="lexical",
                        text=chunk.text,
                        page_start=chunk.page_start,
                        page_end=chunk.page_end,
                        section_path=chunk.section_path,
                        chunker_id=chunk.chunker_id,
                        index_id=index_id,
                        embedding_model_id="",
                        filename=filenames.get(chunk.document_id, ""),
                        content_hash=chunk.content_hash,
                        retrievers=("lexical",),
                        lexical_rank=rank,
                        lexical_score=score,
                        lexical_index_id=index_id,
                    )
                )
        logger.info(
            "lexical_search_completed index_id=%s hits=%s search_ms=%.1f",
            index_id,
            len(hits),
            timer.seconds * 1000,
        )
        return LexicalSearchResult(
            query=query.strip(),
            lexical_index_id=index_id,
            chunker_id=chunker_id,
            hits=tuple(hits),
            search_ms=timer.seconds * 1000,
        )

    def _index_for(
        self, chunker_id: str
    ) -> tuple[BM25Index, dict[str, Chunk], dict[str, str]]:
        rows = self._store.list_chunks_for_chunker(chunker_id)
        fingerprint = _corpus_fingerprint(
            chunker_id,
            rows,
            k1=self._settings.bm25_k1,
            b=self._settings.bm25_b,
        )
        if self._index is not None and self._cache_key == fingerprint:
            return self._index, self._chunks, self._filenames
        documents = [(chunk.chunk_id, tokenize(chunk.text)) for chunk in rows]
        index = BM25Index(
            documents,
            k1=self._settings.bm25_k1,
            b=self._settings.bm25_b,
        )
        chunks = {chunk.chunk_id: chunk for chunk in rows}
        filenames: dict[str, str] = {}
        for chunk in rows:
            if chunk.document_id in filenames:
                continue
            record = self._store.get_by_id(chunk.document_id)
            filenames[chunk.document_id] = record.filename if record else ""
        self._cache_key = fingerprint
        self._index = index
        self._chunks = chunks
        self._filenames = filenames
        return index, chunks, filenames


def _corpus_fingerprint(
    chunker_id: str,
    chunks: list[Chunk],
    *,
    k1: float,
    b: float,
) -> str:
    payload = "|".join(
        f"{chunk.chunk_id}:{chunk.content_hash}"
        for chunk in sorted(chunks, key=lambda item: item.chunk_id)
    )
    raw = f"{chunker_id}|{TOKENIZER_ID}|{k1}|{b}|{payload}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
