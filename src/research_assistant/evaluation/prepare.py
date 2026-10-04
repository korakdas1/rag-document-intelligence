"""Ingest, chunk, and index an evaluation corpus using production services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_assistant.app import Application
from research_assistant.chunking.config import ChunkingConfig, default_config
from research_assistant.core.errors import EvaluationError
from research_assistant.evaluation.identity import corpus_files


def prepare_corpus(
    app: Application,
    corpus_dir: Path,
    *,
    chunking: ChunkingConfig | None = None,
) -> dict[str, Any]:
    directory = Path(corpus_dir)
    config = chunking or default_config()
    files = corpus_files(directory)
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
        "document_ids": sorted(document_ids),
        "chunk_count": len(chunks),
        "indexed_count": indexed.indexed_count,
        "files": [path.name for path in files],
    }
