"""Ingest, chunk, and index an evaluation corpus using production services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_assistant.app import Application
from research_assistant.chunking.config import ChunkingConfig, default_config
from research_assistant.core.errors import EvaluationError


def prepare_corpus(
    app: Application,
    corpus_dir: Path,
    *,
    chunking: ChunkingConfig | None = None,
) -> dict[str, Any]:
    directory = Path(corpus_dir)
    if not directory.is_dir():
        raise EvaluationError(f"Corpus directory missing: {directory}", code="corpus_missing")
    config = chunking or default_config()
    files = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".pdf"}
    )
    if not files:
        raise EvaluationError(f"No documents in {directory}", code="empty_corpus")
    document_ids: list[str] = []
    for path in files:
        ingested = app.ingest.ingest(path)
        if not ingested.ok or ingested.document is None:
            raise EvaluationError(
                f"Failed to ingest {path}: {ingested.error_message}",
                code="ingest_failed",
            )
        chunked = app.chunking.chunk_document(ingested.document.document_id, config)
        if not chunked.ok:
            raise EvaluationError(
                f"Failed to chunk {path}: {chunked.error_message}",
                code="chunk_failed",
            )
        document_ids.append(ingested.document.document_id)
    indexed = app.indexing.index_chunker(config.chunker_id)
    if not indexed.ok:
        raise EvaluationError(
            f"Indexing failed: {indexed.error_message}",
            code="index_failed",
        )
    chunks = app.store.list_chunks_for_chunker(config.chunker_id)
    return {
        "chunker_id": config.chunker_id,
        "index_id": indexed.index_id,
        "embedding_model_id": indexed.embedding_model_id,
        "document_count": len(document_ids),
        "chunk_count": len(chunks),
        "indexed_count": indexed.indexed_count,
        "files": [path.name for path in files],
    }
