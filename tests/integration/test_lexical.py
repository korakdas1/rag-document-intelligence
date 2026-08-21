from pathlib import Path

import pytest

from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.core.errors import RetrievalError
from research_assistant.core.settings import Settings
from research_assistant.core.types import IngestOutcome
from research_assistant.embeddings.hashing import HashingEmbeddingModel
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


def _ingest_lexical_corpus(app):
    cfg = _chunking()
    chunker_id = None
    for path in sorted(LEXICAL.glob("*.md")):
        ingested = app.ingest.ingest(path)
        assert ingested.document is not None
        chunked = app.chunking.chunk_document(ingested.document.document_id, cfg)
        chunker_id = chunked.chunker_id
    assert chunker_id is not None
    return chunker_id


def test_exact_identifier_and_rare_term(tmp_path: Path) -> None:
    app = _app(tmp_path)
    chunker_id = _ingest_lexical_corpus(app)
    error = app.lexical.search("ERR_CONNECTION_REFUSED", chunker_id=chunker_id, top_k=3)
    assert error.hits
    assert "ERR_CONNECTION_REFUSED" in error.hits[0].text
    rare = app.lexical.search("XRQ-917-BETA", chunker_id=chunker_id, top_k=3)
    assert "XRQ-917-BETA" in rare.hits[0].text
    semantic = app.lexical.search("self attention transformer", chunker_id=chunker_id, top_k=3)
    assert "transformer" in semantic.hits[0].text.lower()


def test_empty_query_is_explicit(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with pytest.raises(RetrievalError) as exc:
        app.lexical.search("  ", chunker_id="structure.v1:x")
    assert exc.value.code == "empty_query"


def test_missing_lexical_index_is_explicit(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with pytest.raises(RetrievalError) as exc:
        app.lexical.search("transformer", chunker_id="structure.v1:missing")
    assert exc.value.code == "missing_lexical_index"


def test_lexical_idempotent_and_deterministic(tmp_path: Path) -> None:
    app = _app(tmp_path)
    chunker_id = _ingest_lexical_corpus(app)
    first = app.lexical.search("transformer", chunker_id=chunker_id, top_k=3)
    second = app.lexical.search("transformer", chunker_id=chunker_id, top_k=3)
    assert [hit.chunk_id for hit in first.hits] == [hit.chunk_id for hit in second.hits]
    assert [hit.score for hit in first.hits] == [hit.score for hit in second.hits]


def test_changed_content_drops_stale_lexical_entry(tmp_path: Path) -> None:
    app = _app(tmp_path)
    path = tmp_path / "note.md"
    path.write_text("# One\n\nToken ZEBRAQID lives here.\n", encoding="utf-8")
    first = app.ingest.ingest(path)
    assert first.document is not None
    cfg = _chunking()
    chunked = app.chunking.chunk_document(first.document.document_id, cfg)
    ranked = app.lexical.search("ZEBRAQID", chunker_id=chunked.chunker_id, top_k=3)
    assert ranked.hits
    assert "ZEBRAQID" in ranked.hits[0].text
    path.write_text("# Two\n\nToken YAKQID replaced it.\n", encoding="utf-8")
    updated = app.ingest.ingest(path)
    assert updated.outcome is IngestOutcome.UPDATED
    app.chunking.chunk_document(first.document.document_id, cfg)
    after = app.lexical.search("ZEBRAQID", chunker_id=chunked.chunker_id, top_k=3)
    assert after.hits == ()
    kept = app.lexical.search("YAKQID", chunker_id=chunked.chunker_id, top_k=3)
    assert kept.hits
    assert "YAKQID" in kept.hits[0].text


def test_different_chunkers_do_not_mix(tmp_path: Path) -> None:
    app = _app(tmp_path)
    ingested = app.ingest.ingest(LEXICAL / "transformer.md")
    assert ingested.document is not None
    structure = _chunking()
    window = ChunkingConfig(
        strategy="window",
        target_chars=80,
        max_chars=120,
        min_chars=10,
        overlap_chars=10,
    )
    a = app.chunking.chunk_document(ingested.document.document_id, structure)
    b = app.chunking.chunk_document(ingested.document.document_id, window)
    assert a.chunker_id != b.chunker_id
    assert app.lexical.lexical_index_id(a.chunker_id) != app.lexical.lexical_index_id(
        b.chunker_id
    )
    hit_a = app.lexical.search("transformer", chunker_id=a.chunker_id, top_k=5)
    assert all(hit.chunker_id == a.chunker_id for hit in hit_a.hits)
