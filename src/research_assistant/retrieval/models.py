"""Dense retrieval hit. Hybrid/lexical reuse this shape."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    document_id: str
    rank: int
    score: float
    retriever: str
    text: str
    page_start: int | None
    page_end: int | None
    section_path: tuple[str, ...]
    chunker_id: str
    index_id: str
    embedding_model_id: str
    filename: str = ""
    content_hash: str = ""
    retrievers: tuple[str, ...] = ()
    dense_rank: int | None = None
    lexical_rank: int | None = None
    dense_score: float | None = None
    lexical_score: float | None = None
    fused_score: float | None = None
    lexical_index_id: str = ""
    rerank_score: float | None = None
    rerank_rank: int | None = None
    reranker_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "rank": self.rank,
            "score": self.score,
            "retriever": self.retriever,
            "retrievers": list(self.retrievers or ((self.retriever,) if self.retriever else ())),
            "text": self.text,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section_path": list(self.section_path),
            "chunker_id": self.chunker_id,
            "index_id": self.index_id,
            "embedding_model_id": self.embedding_model_id,
            "filename": self.filename,
            "content_hash": self.content_hash,
            "dense_rank": self.dense_rank,
            "lexical_rank": self.lexical_rank,
            "dense_score": self.dense_score,
            "lexical_score": self.lexical_score,
            "fused_score": self.fused_score,
            "lexical_index_id": self.lexical_index_id,
            "rerank_score": self.rerank_score,
            "rerank_rank": self.rerank_rank,
            "reranker_id": self.reranker_id,
        }
