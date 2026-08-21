from pathlib import Path

import pytest

from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.core.errors import RetrievalError
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from tests.conftest import FIXTURES


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


def _small_chunking() -> ChunkingConfig:
    return ChunkingConfig(
        strategy="structure",
        target_chars=80,
        max_chars=140,
        min_chars=20,
        overlap_chars=15,
    )


def _stack(tmp_path: Path):
    settings = _settings(tmp_path)
    app = create_application(
        settings,
        embedder=HashingEmbeddingModel(dimension=32),
    )
    return app.ingest, app.chunking, app.indexing, app.search, app.store


def test_index_idempotent_and_payload_round_trip(tmp_path: Path) -> None:
    ingest, chunking, indexing, search, store = _stack(tmp_path)
    ingested = ingest.ingest(FIXTURES / "markdown" / "structure.md")
    assert ingested.document is not None
    cfg = _small_chunking()
    chunked = chunking.chunk_document(ingested.document.document_id, cfg)
    first = indexing.index_document(ingested.document.document_id, chunked.chunker_id)
    second = indexing.index_document(ingested.document.document_id, chunked.chunker_id)
    assert first.ok and second.ok
    assert first.indexed_count == second.indexed_count
    meta = store.get_vector_index(first.index_id)
    assert meta is not None
    assert meta.chunk_count == first.indexed_count
    result = search.search(
        "markdown heading list",
        chunker_id=chunked.chunker_id,
        top_k=3,
    )
    assert result.hits
    hit = result.hits[0]
    assert hit.retriever == "dense"
    assert hit.document_id == ingested.document.document_id
    assert hit.section_path is not None
    indexing.vector_store.close()


def test_stale_vectors_removed_when_chunks_shrink(tmp_path: Path) -> None:
    ingest, chunking, indexing, search, store = _stack(tmp_path)
    ingested = ingest.ingest(FIXTURES / "markdown" / "long_article.md")
    assert ingested.document is not None
    cfg = _small_chunking()
    chunked = chunking.chunk_document(ingested.document.document_id, cfg)
    indexing.index_document(ingested.document.document_id, chunked.chunker_id)
    original_ids = {chunk.chunk_id for chunk in chunked.chunks}
    kept = chunked.chunks[:1]
    store.replace_chunks(ingested.document.document_id, chunked.chunker_id, kept)
    indexing.index_document(ingested.document.document_id, chunked.chunker_id)
    remaining = set(
        indexing.vector_store.list_chunk_ids(
            f"idx_{indexing.index_id_for_chunker(chunked.chunker_id)}",
            document_id=ingested.document.document_id,
        )
    )
    assert remaining == {kept[0].chunk_id}
    assert not (original_ids - {kept[0].chunk_id}) & remaining
    indexing.vector_store.close()


def test_changed_content_purges_vectors(tmp_path: Path) -> None:
    ingest, chunking, indexing, search, store = _stack(tmp_path)
    path = tmp_path / "note.md"
    path.write_text("# One\n\n" + ("alpha neural network " * 20), encoding="utf-8")
    first = ingest.ingest(path)
    assert first.document is not None
    cfg = _small_chunking()
    chunked = chunking.chunk_document(first.document.document_id, cfg)
    indexed = indexing.index_document(first.document.document_id, chunked.chunker_id)
    assert indexed.indexed_count
    path.write_text("# Two\n\n" + ("beta cooking recipe " * 20), encoding="utf-8")
    ingest.ingest(path)
    ids = indexing.vector_store.list_chunk_ids(
        f"idx_{indexed.index_id}",
        document_id=first.document.document_id,
    )
    assert ids == []
    indexing.vector_store.close()


def test_dense_search_ranks_lexical_overlap_above_distractor(tmp_path: Path) -> None:
    ingest, chunking, indexing, search, store = _stack(tmp_path)
    relevant = tmp_path / "ml.md"
    distractor = tmp_path / "cake.md"
    relevant.write_text(
        "# ML\n\nGradient descent trains neural networks by minimizing loss.\n",
        encoding="utf-8",
    )
    distractor.write_text(
        "# Cake\n\nBake the chocolate cake at three hundred fifty degrees.\n",
        encoding="utf-8",
    )
    cfg = ChunkingConfig(
        strategy="structure",
        target_chars=400,
        max_chars=500,
        min_chars=10,
        overlap_chars=0,
    )
    rel = ingest.ingest(relevant)
    dist = ingest.ingest(distractor)
    assert rel.document and dist.document
    rel_chunks = chunking.chunk_document(rel.document.document_id, cfg)
    dist_chunks = chunking.chunk_document(dist.document.document_id, cfg)
    assert rel_chunks.chunker_id == dist_chunks.chunker_id
    indexing.index_document(rel.document.document_id, rel_chunks.chunker_id)
    indexing.index_document(dist.document.document_id, dist_chunks.chunker_id)
    result = search.search(
        "training neural networks with gradient descent",
        chunker_id=rel_chunks.chunker_id,
        top_k=2,
    )
    assert result.hits
    assert result.hits[0].document_id == rel.document.document_id
    assert "gradient" in result.hits[0].text.lower()
    indexing.vector_store.close()


def test_empty_query_is_explicit(tmp_path: Path) -> None:
    _, _, indexing, search, _ = _stack(tmp_path)
    with pytest.raises(RetrievalError) as exc:
        search.search("  ", chunker_id="structure.v1:missing")
    assert exc.value.code == "empty_query"
    indexing.vector_store.close()


def test_missing_index_is_explicit(tmp_path: Path) -> None:
    _, _, indexing, search, _ = _stack(tmp_path)
    with pytest.raises(RetrievalError) as exc:
        search.search("hello", chunker_id="structure.v1:does-not-exist")
    assert exc.value.code == "missing_index"
    indexing.vector_store.close()


def test_different_chunker_uses_separate_index(tmp_path: Path) -> None:
    ingest, chunking, indexing, _, store = _stack(tmp_path)
    ingested = ingest.ingest(FIXTURES / "markdown" / "structure.md")
    assert ingested.document is not None
    structure = ChunkingConfig(
        strategy="structure",
        target_chars=80,
        max_chars=140,
        min_chars=20,
        overlap_chars=15,
    )
    window = ChunkingConfig(
        strategy="window",
        target_chars=60,
        max_chars=90,
        min_chars=15,
        overlap_chars=10,
    )
    a = chunking.chunk_document(ingested.document.document_id, structure)
    b = chunking.chunk_document(ingested.document.document_id, window)
    ra = indexing.index_document(ingested.document.document_id, a.chunker_id)
    rb = indexing.index_document(ingested.document.document_id, b.chunker_id)
    assert ra.index_id != rb.index_id
    indexing.vector_store.close()
