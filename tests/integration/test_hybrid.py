from pathlib import Path

import pytest

from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.core.errors import RetrievalError
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
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
        rrf_k=60,
        reranker_model_name="overlap",
    )


def _app(tmp_path: Path):
    return create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
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


def test_modes_dense_lexical_hybrid(tmp_path: Path) -> None:
    app = _app(tmp_path)
    chunker_id = _index_corpus(app)
    dense = app.hybrid.search(
        "ERR_CONNECTION_REFUSED", chunker_id=chunker_id, mode="dense", top_k=3
    )
    lexical = app.hybrid.search(
        "ERR_CONNECTION_REFUSED", chunker_id=chunker_id, mode="lexical", top_k=3
    )
    hybrid = app.hybrid.search(
        "ERR_CONNECTION_REFUSED", chunker_id=chunker_id, mode="hybrid", top_k=3
    )
    assert dense.mode == "dense"
    assert lexical.mode == "lexical"
    assert hybrid.mode == "hybrid"
    assert lexical.hits and "ERR_CONNECTION_REFUSED" in lexical.hits[0].text
    assert hybrid.hits
    assert hybrid.diagnostics.fusion == "rrf.v1"
    ids = [hit.chunk_id for hit in hybrid.hits]
    assert len(ids) == len(set(ids))
    both = [hit for hit in hybrid.hits if hit.dense_rank and hit.lexical_rank]
    assert both or hybrid.hits[0].lexical_rank == 1


def test_hybrid_final_top_k_and_diagnostics(tmp_path: Path) -> None:
    app = _app(tmp_path)
    chunker_id = _index_corpus(app)
    result = app.hybrid.search(
        "transformer architecture",
        chunker_id=chunker_id,
        mode="hybrid",
        top_k=2,
        dense_candidate_k=8,
        lexical_candidate_k=8,
    )
    assert len(result.hits) <= 2
    assert result.diagnostics.final_top_k == 2
    assert result.diagnostics.dense_candidate_k == 8
    assert result.diagnostics.lexical_candidate_k == 8
    assert result.hits[0].rank == 1
    assert result.hits[0].fused_score is not None


def test_unsupported_mode(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with pytest.raises(RetrievalError) as exc:
        app.hybrid.search("q", chunker_id="x", mode="rerank")
    assert exc.value.code == "unsupported_mode"


def test_hybrid_does_not_fallback_when_dense_missing(tmp_path: Path) -> None:
    app = _app(tmp_path)
    ingested = app.ingest.ingest(LEXICAL / "transformer.md")
    assert ingested.document is not None
    chunked = app.chunking.chunk_document(ingested.document.document_id, _chunking())
    with pytest.raises(RetrievalError) as exc:
        app.hybrid.search(
            "transformer",
            chunker_id=chunked.chunker_id,
            mode="hybrid",
        )
    assert exc.value.code == "missing_index"


def test_filter_propagates_to_all_modes(tmp_path: Path) -> None:
    app = _app(tmp_path)
    cfg = _chunking()
    docs = {}
    for name in ("transformer.md", "error_code.md"):
        ingested = app.ingest.ingest(LEXICAL / name)
        assert ingested.document is not None
        chunked = app.chunking.chunk_document(ingested.document.document_id, cfg)
        app.indexing.index_document(ingested.document.document_id, chunked.chunker_id)
        docs[name] = (ingested.document.document_id, chunked.chunker_id)
    chunker_id = docs["transformer.md"][1]
    target = docs["error_code.md"][0]
    filt = RetrievalFilter(document_ids=(target,))
    for mode in ("dense", "lexical", "hybrid"):
        result = app.hybrid.search(
            "error transformer",
            chunker_id=chunker_id,
            mode=mode,
            top_k=5,
            filters=filt,
        )
        assert all(hit.document_id == target for hit in result.hits)
    app.indexing.vector_store.close()


def test_cli_module_does_not_own_bm25() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "research_assistant"
        / "cli.py"
    ).read_text(encoding="utf-8")
    assert "BM25Index" not in source
    assert "tokenize(" not in source
    assert "create_application" in source
