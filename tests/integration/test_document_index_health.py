"""Per-document readiness and retrieval must survive partial indexing failures."""

from dataclasses import replace
import sqlite3

import pytest

from research_assistant.api.errors import ApiError
from research_assistant.api.library import DocumentLibrary
from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.core.errors import EmbeddingError, VectorStoreError
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.indexing.identity import collection_name_for
from research_assistant.indexing.models import VectorRecord
from research_assistant.indexing.qdrant_store import QdrantVectorStore
from research_assistant.retrieval.filters import RetrievalFilter
from research_assistant.storage.sqlite import SqliteDocumentStore


class FailingEmbedder(HashingEmbeddingModel):
    fail = False
    calls = 0

    def embed_documents(self, texts):
        self.calls += 1
        if self.fail:
            raise EmbeddingError("Injected embedding failure", code="embedding_failed")
        return super().embed_documents(texts)


@pytest.fixture
def failed_document(settings, tmp_path):
    embedder = FailingEmbedder()
    app = create_application(settings, embedder=embedder)
    library = DocumentLibrary(app)

    def add(name):
        path = tmp_path / f"{name}.md"
        path.write_text(f"# {name}\n\n{name} unique searchable evidence.\n")
        return library.ingest_and_index(path).summary.document_id

    a = add("alpha")
    embedder.fail = True
    with pytest.raises(ApiError):
        add("bravo")
    b = next(doc.document_id for doc in app.store.list_documents() if doc.filename == "bravo.md")
    assert library.get_document(b).status != "ready"
    embedder.fail = False
    c = add("charlie")
    collection = collection_name_for(app.indexing.index_id_for_chunker(library.chunker_id))
    assert app.store.count_chunks(b, library.chunker_id) > 0
    assert app.indexing.vector_store.list_chunk_ids(collection, document_id=b) == []
    yield app, library, embedder, a, b, c
    app.indexing.vector_store.close()


def test_failed_document_does_not_inherit_other_documents_readiness(failed_document):
    app, library, _, a, b, c = failed_document
    states = {doc.document_id: doc.status for doc in library.list_documents()}
    assert states[a] == states[c] == "ready"
    assert states[b] != "ready"
    assert library.get_document(b).status != "ready"


def test_reindex_repairs_failed_document_before_becoming_idempotent(failed_document):
    app, library, embedder, _, b, _ = failed_document
    before = embedder.calls
    repaired = library.reindex_document(b)
    assert embedder.calls > before
    assert repaired.outcome == "updated"
    assert repaired.summary.status == "ready"
    collection = collection_name_for(app.indexing.index_id_for_chunker(library.chunker_id))
    expected = {chunk.chunk_id for chunk in app.store.list_chunks(b, library.chunker_id)}
    assert set(app.indexing.vector_store.list_chunk_ids(collection, document_id=b)) == expected
    before = embedder.calls
    assert library.reindex_document(b).outcome == "unchanged"
    assert embedder.calls == before
    for mode in ("dense", "lexical", "hybrid"):
        hits = app.hybrid.search("bravo", chunker_id=library.chunker_id, mode=mode).hits
        assert b in {hit.document_id for hit in hits}


@pytest.mark.parametrize("mode", ["dense", "lexical", "hybrid"])
def test_incomplete_document_is_excluded_from_retrieval(failed_document, mode):
    app, library, _, _, b, _ = failed_document
    result = app.hybrid.search("bravo", chunker_id=library.chunker_id, mode=mode)
    assert b not in {hit.document_id for hit in result.hits}


class PartialWriter(QdrantVectorStore):
    fault: str | None = None

    def upsert(self, collection_name, records):
        if self.fault == "partial":
            super().upsert(collection_name, records[:1])
            raise VectorStoreError("Injected partial write")
        if self.fault == "silent_drop":
            super().upsert(collection_name, records[:1])
            return
        super().upsert(collection_name, records)
        if self.fault == "after_write":
            raise VectorStoreError("Injected failure after writing every point")


@pytest.fixture
def multi_document(settings, tmp_path):
    vectors = PartialWriter(settings.vector_index_path)
    app = create_application(settings, embedder=HashingEmbeddingModel(), vector_store=vectors)
    config = ChunkingConfig(target_chars=80, max_chars=120, min_chars=20, overlap_chars=0)
    library = DocumentLibrary(app, chunking=config)
    path = tmp_path / "many.md"
    path.write_text("# Bravo\n\n" + "\n\n".join(
        f"Bravo fact {i}: the search index contains independently verifiable evidence."
        for i in range(8)
    ))
    doc_id = library.ingest_and_index(path).summary.document_id
    assert app.store.count_chunks(doc_id, config.chunker_id) > 1
    yield app, library, vectors, doc_id, config
    vectors.close()


def assert_excluded(app, library, doc_id):
    assert library.get_document(doc_id).status == "failed"
    assert library.get_document(doc_id).error_message
    for mode in ("dense", "lexical", "hybrid"):
        hits = app.hybrid.search("Bravo", chunker_id=library.chunker_id, mode=mode).hits
        assert doc_id not in {hit.document_id for hit in hits}


@pytest.mark.parametrize("fault", ["partial", "after_write", "silent_drop"])
def test_partial_or_unacknowledged_writes_remain_inactive(multi_document, fault):
    app, library, vectors, doc_id, _ = multi_document
    # Prime the lexical cache before invalidating the document.
    assert app.lexical.search("Bravo", chunker_id=library.chunker_id).hits
    vectors.fault = fault
    result = app.indexing.index_document(doc_id, library.chunker_id)
    assert not result.ok
    health = app.indexing.health.document_index_health(doc_id, library.chunker_id)
    assert health.actual_ids
    if fault == "after_write":
        assert health.actual_ids == health.expected_ids  # counts/IDs alone are insufficient
    else:
        assert health.missing_ids
    assert_excluded(app, library, doc_id)
    vectors.fault = None
    assert library.reindex_document(doc_id).summary.status == "ready"
    assert app.lexical.search("Bravo", chunker_id=library.chunker_id).hits


@pytest.mark.parametrize("damage", ["missing", "extra", "same_count_stale", "wrong_chunker", "wrong_hash"])
def test_reindex_reconciles_exact_vector_identity(multi_document, damage):
    app, library, vectors, doc_id, _ = multi_document
    health = app.indexing.health.document_index_health(doc_id, library.chunker_id)
    collection = collection_name_for(health.index_id)
    payload = vectors.list_payloads(collection, document_id=doc_id)[0]
    if damage in {"missing", "same_count_stale"}:
        vectors.delete_ids(collection, [payload.chunk_id])
    if damage != "missing":
        if damage in {"extra", "same_count_stale"}:
            changed = replace(payload, chunk_id="stale-chunk")
        elif damage == "wrong_chunker":
            changed = replace(payload, chunker_id="different-chunker")
        else:
            changed = replace(payload, content_hash="different-content")
        vectors.upsert(collection, [VectorRecord(changed.chunk_id, [1.0] + [0.0] * 31, changed)])
    broken = app.indexing.health.document_index_health(doc_id, library.chunker_id)
    assert not broken.ready
    if damage == "same_count_stale":
        assert len(broken.expected_ids) == len(broken.actual_ids)
        assert broken.missing_ids and broken.stale_ids
    assert_excluded(app, library, doc_id)
    assert library.reindex_document(doc_id).summary.status == "ready"
    fixed = app.indexing.health.document_index_health(doc_id, library.chunker_id)
    assert fixed.expected_ids == fixed.actual_ids == health.expected_ids
    assert fixed.ready


def test_failure_truth_survives_restart_and_other_success(failed_document):
    app, library, _, a, b, c = failed_document
    app.indexing.vector_store.close()
    restarted = create_application(app.settings, embedder=HashingEmbeddingModel())
    try:
        recovered = DocumentLibrary(restarted)
        assert_excluded(restarted, recovered, b)
        assert recovered.get_document(a).status == recovered.get_document(c).status == "ready"
        assert recovered.reindex_document(b).summary.status == "ready"
    finally:
        restarted.indexing.vector_store.close()


def test_failed_activation_cannot_be_overridden_by_complete_vectors(multi_document, monkeypatch):
    app, library, vectors, doc_id, config = multi_document

    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError("Injected database outage during activation")

    monkeypatch.setattr(app.store, "finish_document_indexes", unavailable)
    assert not app.indexing.index_document(doc_id, config.chunker_id).ok
    health = app.indexing.health.document_index_health(doc_id, config.chunker_id)
    assert health.status == "building"
    assert health.actual_ids == health.expected_ids
    assert not health.ready
    vectors.close()
    restarted = create_application(app.settings, embedder=HashingEmbeddingModel())
    try:
        recovered = DocumentLibrary(restarted, chunking=config)
        assert recovered.get_document(doc_id).status != "ready"
        for mode in ("dense", "lexical", "hybrid"):
            assert not restarted.hybrid.search("Bravo", chunker_id=config.chunker_id, mode=mode).hits
        assert recovered.reindex_document(doc_id).summary.status == "ready"
    finally:
        restarted.indexing.vector_store.close()


@pytest.mark.parametrize("repair", [False, True])
def test_delete_partial_or_repaired_document_removes_representation(multi_document, repair):
    app, library, vectors, doc_id, config = multi_document
    vectors.fault = "partial"
    assert not app.indexing.index_document(doc_id, config.chunker_id).ok
    vectors.fault = None
    if repair:
        assert library.reindex_document(doc_id).summary.status == "ready"
    index_id = app.indexing.index_id_for_chunker(config.chunker_id)
    assert library.delete_document(doc_id).deleted
    assert not app.store.list_chunks(doc_id)
    assert doc_id not in app.store.list_document_indexes(index_id)
    assert not vectors.list_payloads(collection_name_for(index_id), document_id=doc_id)
    assert doc_id not in app.indexing.health.searchable_document_ids(config.chunker_id)


def test_failure_does_not_disable_healthy_document_or_bypass_subset(failed_document):
    app, library, embedder, a, b, _ = failed_document
    embedder.fail = True
    assert not app.indexing.index_document(b, library.chunker_id).ok
    assert library.get_document(a).status == "ready"
    for mode in ("dense", "lexical", "hybrid"):
        healthy = app.hybrid.search("alpha", chunker_id=library.chunker_id, mode=mode,
                                   filters=RetrievalFilter(document_ids=(a,))).hits
        assert healthy and {hit.document_id for hit in healthy} == {a}
        failed = app.hybrid.search("alpha bravo", chunker_id=library.chunker_id, mode=mode,
                                  filters=RetrievalFilter(document_ids=(b,))).hits
        assert not failed


def test_library_batches_vector_inventory(failed_document, monkeypatch):
    app, library, _, _, b, _ = failed_document
    calls = []
    original = app.indexing.vector_store.list_payloads

    def counted(*args, **kwargs):
        calls.append(kwargs.get("document_id"))
        return original(*args, **kwargs)

    monkeypatch.setattr(app.indexing.vector_store, "list_payloads", counted)
    library.list_documents()
    assert calls == [None]
    library.get_document(b)
    assert calls == [None, b]


def test_v4_migration_preserves_data_and_checks_legacy_vectors(failed_document):
    app, library, _, a, b, c = failed_document
    session = app.store.create_session("existing-session", title="Existing", created_at="2026-01-01")
    with sqlite3.connect(app.settings.database_path) as conn:
        conn.execute(
            """INSERT INTO conversation_turns
               (turn_id, session_id, sequence, question, grounding_status, created_at, sources_json)
               VALUES ('old-turn', 'existing-session', 1, 'An existing question',
                       'GROUNDED', '2026-01-01', '[{"text":"retained source"}]')"""
        )
        # Recreate the exact pre-migration schema while retaining the corpus.
        conn.execute("DROP TABLE document_indexes")
        conn.execute("UPDATE schema_version SET version = 4")
    migrated = SqliteDocumentStore(app.settings.database_path)
    assert migrated.schema_version() == 5
    assert migrated.get_session("existing-session").title == session.title
    assert migrated.get_turn("old-turn").sources_json == '[{"text":"retained source"}]'
    assert len(migrated.list_documents()) == 3
    assert library.get_document(a).status == library.get_document(c).status == "ready"
    assert_excluded(app, library, b)
    index_id = app.indexing.index_id_for_chunker(library.chunker_id)
    states = migrated.list_document_indexes(index_id)
    SqliteDocumentStore(app.settings.database_path)
    assert migrated.list_document_indexes(index_id) == states
    assert library.reindex_document(b).summary.status == "ready"


def test_migration_rolls_back_before_advancing_version(failed_document, monkeypatch):
    app, _, _, a, _, _ = failed_document
    with sqlite3.connect(app.settings.database_path) as conn:
        conn.execute("DROP TABLE document_indexes")
        conn.execute("UPDATE schema_version SET version = 4")
    migrate = SqliteDocumentStore._migrate_document_indexes

    def interrupted(conn):
        migrate(conn)
        raise RuntimeError("Injected migration interruption")

    with monkeypatch.context() as scoped:
        scoped.setattr(SqliteDocumentStore, "_migrate_document_indexes", staticmethod(interrupted))
        with pytest.raises(RuntimeError, match="Injected migration"):
            SqliteDocumentStore(app.settings.database_path)
    with sqlite3.connect(app.settings.database_path) as conn:
        assert conn.execute("SELECT version FROM schema_version").fetchone()[0] == 4
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name = 'document_indexes'").fetchall()
    restored = SqliteDocumentStore(app.settings.database_path)
    assert restored.schema_version() == 5
    assert restored.get_by_id(a)


def test_partial_points_stay_inactive_after_restart(multi_document):
    app, library, vectors, doc_id, config = multi_document
    vectors.fault = "partial"
    assert not app.indexing.index_document(doc_id, config.chunker_id).ok
    vectors.close()
    restarted = create_application(app.settings, embedder=HashingEmbeddingModel())
    try:
        recovered = DocumentLibrary(restarted, chunking=config)
        assert_excluded(restarted, recovered, doc_id)
        assert recovered.reindex_document(doc_id).summary.status == "ready"
    finally:
        restarted.indexing.vector_store.close()


def test_collection_rebuild_failure_requires_repair_of_each_document(failed_document):
    app, library, embedder, a, b, c = failed_document
    embedder.fail = True
    assert not app.indexing.index_chunker(library.chunker_id).ok
    assert all(doc.status != "ready" for doc in library.list_documents())
    embedder.fail = False
    assert library.reindex_document(a).summary.status == "ready"
    assert library.get_document(b).status != "ready"
    assert library.get_document(c).status != "ready"
    assert not app.lexical.search("charlie", chunker_id=library.chunker_id).hits
    assert app.indexing.index_chunker(library.chunker_id).ok
    assert all(doc.status == "ready" for doc in library.list_documents())


def test_api_exposes_document_failure_and_successful_repair(failed_document):
    from fastapi.testclient import TestClient
    from research_assistant.api.app import create_api

    app, _, _, _, b, _ = failed_document
    with TestClient(create_api(app)) as client:
        rows = client.get("/api/documents").json()["documents"]
        assert next(doc for doc in rows if doc["document_id"] == b)["status"] == "failed"
        detail = client.get(f"/api/documents/{b}").json()
        assert detail["index_status"] == "failed"
        assert "Re-index" in detail["error_message"]
        assert "Injected" not in detail["error_message"]
        fixed = client.post(f"/api/documents/{b}/reindex")
        assert fixed.status_code == 200
        assert fixed.json()["document"]["status"] == "ready"
        assert fixed.json()["outcome"] == "updated"
        assert client.post(f"/api/documents/{b}/reindex").json()["outcome"] == "unchanged"
