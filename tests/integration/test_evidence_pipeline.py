from pathlib import Path

from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.reranking.overlap import OverlapReranker
from research_assistant.retrieval.filters import RetrievalFilter
from tests.conftest import FIXTURES

LEXICAL = FIXTURES / "lexical"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "docs.db",
        log_level="WARNING",
        max_file_bytes=50 * 1024 * 1024,
        embedding_model_name="hashing",
        embedding_device="cpu",
        vector_index_path=tmp_path / "qdrant",
        default_top_k=5,
        dense_candidate_k=10,
        lexical_candidate_k=10,
        reranker_model_name="overlap",
        rerank_candidate_k=8,
        rerank_top_k=5,
        max_context_tokens=256,
        rrf_k=60,
    )


def _app(tmp_path: Path):
    return create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
    )


def _chunking() -> ChunkingConfig:
    return ChunkingConfig(
        strategy="structure",
        target_chars=400,
        max_chars=600,
        min_chars=10,
        overlap_chars=0,
    )


def _index_corpus(app):
    cfg = _chunking()
    chunker_id = None
    for path in sorted(LEXICAL.glob("*.md")):
        ingested = app.ingest.ingest(path)
        assert ingested.document is not None
        chunked = app.chunking.chunk_document(ingested.document.document_id, cfg)
        chunker_id = chunked.chunker_id
        app.indexing.index_document(ingested.document.document_id, chunker_id)
    assert chunker_id is not None
    return chunker_id


def test_evidence_pipeline_hybrid_rerank_context(tmp_path: Path) -> None:
    app = _app(tmp_path)
    chunker_id = _index_corpus(app)
    result = app.evidence.collect(
        "ERR_CONNECTION_REFUSED",
        chunker_id=chunker_id,
        mode="hybrid",
        rerank_top_k=4,
        max_context_tokens=200,
    )
    assert result.search.mode == "hybrid"
    assert result.rerank.diagnostics.enabled is True
    assert result.rerank.hits
    assert result.rerank.hits[0].rerank_rank == 1
    assert result.rerank.hits[0].rank >= 1
    assert "ERR_CONNECTION_REFUSED" in result.rerank.hits[0].text
    assert result.context.items
    assert result.context.items[0].citation_id == "S1"
    assert result.context.diagnostics.estimated_tokens <= 200
    citation_chunks = {item.source.chunk_id for item in result.context.items}
    rerank_chunks = {hit.chunk_id for hit in result.rerank.hits}
    assert citation_chunks <= rerank_chunks


def test_pipeline_respects_document_filter(tmp_path: Path) -> None:
    app = _app(tmp_path)
    chunker_id = _index_corpus(app)
    ingested = app.ingest.ingest(LEXICAL / "transformer.md")
    assert ingested.document is not None
    allowed = ingested.document.document_id
    result = app.evidence.collect(
        "transformer architecture",
        chunker_id=chunker_id,
        filters=RetrievalFilter(document_ids=(allowed,)),
    )
    assert result.search.hits
    assert all(hit.document_id == allowed for hit in result.search.hits)
    assert all(hit.document_id == allowed for hit in result.rerank.hits)
    assert all(item.source.document_id == allowed for item in result.context.items)


def test_pipeline_stale_lexical_after_content_change(tmp_path: Path) -> None:
    app = _app(tmp_path)
    source = tmp_path / "note.md"
    source.write_text("# Note\n\nSECRET_TOKEN_ALPHA is documented here.\n", encoding="utf-8")
    ingested = app.ingest.ingest(source)
    assert ingested.document is not None
    chunked = app.chunking.chunk_document(ingested.document.document_id, _chunking())
    app.indexing.index_document(ingested.document.document_id, chunked.chunker_id)
    before = app.evidence.collect(
        "SECRET_TOKEN_ALPHA",
        chunker_id=chunked.chunker_id,
        mode="hybrid",
    )
    assert any("SECRET_TOKEN_ALPHA" in hit.text for hit in before.rerank.hits)
    source.write_text("# Note\n\nThe secret was rotated.\n", encoding="utf-8")
    updated = app.ingest.ingest(source)
    assert updated.ok
    chunked = app.chunking.chunk_document(ingested.document.document_id, _chunking())
    app.indexing.index_document(ingested.document.document_id, chunked.chunker_id)
    after = app.evidence.collect(
        "SECRET_TOKEN_ALPHA",
        chunker_id=chunked.chunker_id,
        mode="hybrid",
    )
    assert all("SECRET_TOKEN_ALPHA" not in hit.text for hit in after.search.hits)
    assert all("SECRET_TOKEN_ALPHA" not in hit.text for hit in after.rerank.hits)
    assert all("SECRET_TOKEN_ALPHA" not in item.text for item in after.context.items)
