"""Stale-vector cleanup is an application-service concern, not CLI wiring."""

from __future__ import annotations

from pathlib import Path

from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.core.errors import VectorStoreError
from research_assistant.core.settings import Settings
from research_assistant.core.types import IngestOutcome, VectorPurgeStatus
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.indexing.identity import collection_name_for
from research_assistant.indexing.invalidation import RegistryVectorInvalidator
from research_assistant.ingestion.service import IngestionService
from research_assistant.storage.sqlite import SqliteDocumentStore


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


def _chunking() -> ChunkingConfig:
    return ChunkingConfig(
        strategy="structure",
        target_chars=80,
        max_chars=140,
        min_chars=20,
        overlap_chars=15,
    )


def _app(tmp_path: Path):
    return create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
    )


def _write_note(path: Path, heading: str, token: str) -> None:
    path.write_text(f"# {heading}\n\n" + (f"{token} " * 24), encoding="utf-8")


def test_service_path_purges_stale_vectors_without_cli(tmp_path: Path) -> None:
    app = _app(tmp_path)
    path = tmp_path / "note.md"
    _write_note(path, "One", "alpha neural network")
    first = app.ingest.ingest(path)
    assert first.document is not None
    chunked = app.chunking.chunk_document(first.document.document_id, _chunking())
    indexed = app.indexing.index_document(
        first.document.document_id, chunked.chunker_id
    )
    assert indexed.indexed_count
    _write_note(path, "Two", "beta cooking recipe")
    updated = app.ingest.ingest(path)
    assert updated.outcome is IngestOutcome.UPDATED
    assert updated.ok
    assert updated.vector_purge_status is VectorPurgeStatus.PURGED
    assert updated.vector_purge_error is None
    leftover = app.indexing.vector_store.list_chunk_ids(
        collection_name_for(indexed.index_id),
        document_id=first.document.document_id,
    )
    assert leftover == []
    app.indexing.vector_store.close()


def test_content_change_purges_all_registered_indexes(tmp_path: Path) -> None:
    app = _app(tmp_path)
    path = tmp_path / "note.md"
    _write_note(path, "One", "alpha neural network")
    ingested = app.ingest.ingest(path)
    assert ingested.document is not None
    document_id = ingested.document.document_id
    structure = _chunking()
    window = ChunkingConfig(
        strategy="window",
        target_chars=60,
        max_chars=90,
        min_chars=15,
        overlap_chars=10,
    )
    a = app.chunking.chunk_document(document_id, structure)
    b = app.chunking.chunk_document(document_id, window)
    ra = app.indexing.index_document(document_id, a.chunker_id)
    rb = app.indexing.index_document(document_id, b.chunker_id)
    assert ra.index_id != rb.index_id
    _write_note(path, "Two", "beta cooking recipe")
    updated = app.ingest.ingest(path)
    assert updated.vector_purge_status is VectorPurgeStatus.PURGED
    for index_id in (ra.index_id, rb.index_id):
        assert (
            app.indexing.vector_store.list_chunk_ids(
                collection_name_for(index_id),
                document_id=document_id,
            )
            == []
        )
    app.indexing.vector_store.close()


def test_unrelated_document_vectors_are_kept(tmp_path: Path) -> None:
    app = _app(tmp_path)
    path_a = tmp_path / "a.md"
    path_b = tmp_path / "b.md"
    _write_note(path_a, "Alpha", "neural network training")
    _write_note(path_b, "Beta", "chocolate cake recipe")
    doc_a = app.ingest.ingest(path_a)
    doc_b = app.ingest.ingest(path_b)
    assert doc_a.document and doc_b.document
    cfg = _chunking()
    chunks_a = app.chunking.chunk_document(doc_a.document.document_id, cfg)
    chunks_b = app.chunking.chunk_document(doc_b.document.document_id, cfg)
    assert chunks_a.chunker_id == chunks_b.chunker_id
    indexed_a = app.indexing.index_document(
        doc_a.document.document_id, chunks_a.chunker_id
    )
    app.indexing.index_document(doc_b.document.document_id, chunks_b.chunker_id)
    before_b = set(
        app.indexing.vector_store.list_chunk_ids(
            collection_name_for(indexed_a.index_id),
            document_id=doc_b.document.document_id,
        )
    )
    assert before_b
    _write_note(path_a, "Alpha-2", "gradient descent optimizer")
    updated = app.ingest.ingest(path_a)
    assert updated.vector_purge_status is VectorPurgeStatus.PURGED
    after_a = app.indexing.vector_store.list_chunk_ids(
        collection_name_for(indexed_a.index_id),
        document_id=doc_a.document.document_id,
    )
    after_b = set(
        app.indexing.vector_store.list_chunk_ids(
            collection_name_for(indexed_a.index_id),
            document_id=doc_b.document.document_id,
        )
    )
    assert after_a == []
    assert after_b == before_b
    app.indexing.vector_store.close()


def test_purge_is_idempotent(tmp_path: Path) -> None:
    app = _app(tmp_path)
    path = tmp_path / "note.md"
    _write_note(path, "One", "alpha neural network")
    first = app.ingest.ingest(path)
    assert first.document is not None
    chunked = app.chunking.chunk_document(first.document.document_id, _chunking())
    indexed = app.indexing.index_document(
        first.document.document_id, chunked.chunker_id
    )
    _write_note(path, "Two", "beta cooking recipe")
    updated = app.ingest.ingest(path)
    again = app.indexing.purge_document(first.document.document_id)
    assert updated.vector_purge_status is VectorPurgeStatus.PURGED
    assert again.status is VectorPurgeStatus.PURGED
    assert again.ok
    assert (
        app.indexing.vector_store.list_chunk_ids(
            collection_name_for(indexed.index_id),
            document_id=first.document.document_id,
        )
        == []
    )
    app.indexing.vector_store.close()


def test_cleanup_failure_is_surfaced_and_document_still_updates(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = SqliteDocumentStore(settings.database_path)

    class _FailingStore:
        def collection_exists(self, collection_name: str) -> bool:
            return True

        def delete_by_document(
            self,
            collection_name: str,
            document_id: str,
            chunker_id: str | None = None,
        ) -> None:
            raise VectorStoreError(
                "simulated vector purge failure",
                code="vector_store_error",
            )

        def count(self, collection_name: str) -> int:
            return 0

    app = create_application(
        settings,
        store=store,
        embedder=HashingEmbeddingModel(dimension=32),
    )
    path = tmp_path / "note.md"
    _write_note(path, "One", "alpha neural network")
    first = app.ingest.ingest(path)
    assert first.document is not None
    chunked = app.chunking.chunk_document(first.document.document_id, _chunking())
    app.indexing.index_document(first.document.document_id, chunked.chunker_id)
    failing_ingest = IngestionService(
        settings=settings,
        store=store,
        invalidator=RegistryVectorInvalidator(store, _FailingStore()),
    )
    _write_note(path, "Two", "beta cooking recipe")
    updated = failing_ingest.ingest(path)
    assert updated.outcome is IngestOutcome.UPDATED
    assert updated.ok
    assert updated.vector_purge_status is VectorPurgeStatus.FAILED
    assert updated.vector_purge_error is not None
    assert any(item.startswith("vector_purge_failed:") for item in updated.warnings)
    stored = store.get_by_id(first.document.document_id)
    assert stored is not None
    assert stored.checksum_sha256 != first.document.checksum_sha256
    meta = store.get_vector_index(
        app.indexing.index_id_for_chunker(chunked.chunker_id)
    )
    assert meta is not None
    assert meta.status.value == "ready"
    leftover = app.indexing.vector_store.list_chunk_ids(
        collection_name_for(app.indexing.index_id_for_chunker(chunked.chunker_id)),
        document_id=first.document.document_id,
    )
    assert leftover
    skipped = app.search.search(
        "beta cooking recipe",
        chunker_id=chunked.chunker_id,
        top_k=5,
    )
    assert skipped.hits == ()
    app.indexing.vector_store.close()


def test_search_skips_vector_hits_missing_from_sqlite(tmp_path: Path) -> None:
    app = _app(tmp_path)
    path = tmp_path / "note.md"
    _write_note(path, "ML", "gradient descent neural network")
    ingested = app.ingest.ingest(path)
    assert ingested.document is not None
    chunked = app.chunking.chunk_document(ingested.document.document_id, _chunking())
    indexed = app.indexing.index_document(
        ingested.document.document_id, chunked.chunker_id
    )
    assert indexed.ok
    live = app.search.search(
        "gradient descent neural network",
        chunker_id=chunked.chunker_id,
        top_k=5,
    )
    assert live.hits
    store = app.store
    store.delete_chunks_for_document(ingested.document.document_id)
    stale = app.search.search(
        "gradient descent neural network",
        chunker_id=chunked.chunker_id,
        top_k=5,
    )
    assert stale.hits == ()
    leftover = app.indexing.vector_store.list_chunk_ids(
        collection_name_for(indexed.index_id),
        document_id=ingested.document.document_id,
    )
    assert leftover
    app.indexing.vector_store.close()


def test_cli_module_does_not_own_vector_purge() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "research_assistant"
        / "cli.py"
    ).read_text(encoding="utf-8")
    assert "purge_document" not in source
    assert "delete_by_document" not in source
    assert "on_chunks_invalidated" not in source
    assert "create_application" in source
