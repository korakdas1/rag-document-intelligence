"""Document library delete/reindex keeps retrieval consistent."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from research_assistant.api.app import create_api
from research_assistant.api.library import DocumentLibrary
from research_assistant.app import create_application
from research_assistant.chunking.config import default_config
from research_assistant.core.errors import VectorStoreError
from research_assistant.core.settings import Settings
from research_assistant.core.types import VectorPurgeStatus
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.indexing.identity import collection_name_for
from research_assistant.indexing.invalidation import PurgeResult
from research_assistant.reranking.overlap import OverlapReranker
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
        upload_dir=tmp_path / "uploads",
        default_top_k=5,
        dense_candidate_k=10,
        lexical_candidate_k=10,
        reranker_model_name="overlap",
        rerank_candidate_k=8,
        rerank_top_k=5,
        max_context_tokens=256,
        rrf_k=60,
        llm_provider="scripted",
        llm_model_name="scripted.v1",
    )


def _application(tmp_path: Path):
    return create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=ScriptedLLM(
            '{"answer": "ok [S1].", "insufficient_evidence": false}'
        ),
    )


def _client_for(application) -> TestClient:
    return TestClient(create_api(application))


def _upload(client: TestClient, name: str, data: bytes | None = None) -> dict:
    path = LEXICAL / name
    payload = data if data is not None else path.read_bytes()
    response = client.post(
        "/api/documents",
        files={"file": (name, payload, "text/markdown")},
    )
    assert response.status_code == 200, response.text
    return response.json()["document"]


def _hit_ids(application, query: str, *, mode: str) -> set[str]:
    chunker_id = default_config().chunker_id
    result = application.hybrid.search(query, chunker_id=chunker_id, mode=mode)
    return {hit.document_id for hit in result.hits}


def test_delete_removes_sqlite_chunks_and_search_hits(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    error_doc = _upload(client, "error_code.md")
    cake_doc = _upload(client, "cake.md")
    error_id = error_doc["document_id"]
    cake_id = cake_doc["document_id"]

    assert error_id in _hit_ids(application, "ERR_CONNECTION_REFUSED", mode="lexical")
    assert error_id in _hit_ids(application, "ERR_CONNECTION_REFUSED", mode="dense")

    deleted = client.delete(f"/api/documents/{error_id}")
    assert deleted.status_code == 200, deleted.text
    body = deleted.json()
    assert body["deleted"] is True
    assert body["already_absent"] is False
    assert body["vector_cleanup_status"] == "purged"

    assert application.store.get_by_id(error_id) is None
    assert application.store.count_chunks(error_id) == 0
    listed = {item["document_id"] for item in client.get("/api/documents").json()["documents"]}
    assert error_id not in listed
    assert cake_id in listed

    assert error_id not in _hit_ids(application, "ERR_CONNECTION_REFUSED", mode="lexical")
    assert error_id not in _hit_ids(application, "ERR_CONNECTION_REFUSED", mode="dense")
    assert cake_id in _hit_ids(application, "chocolate cake cocoa", mode="lexical")
    assert cake_id in _hit_ids(application, "chocolate cake cocoa", mode="dense")

    index_id = application.indexing.index_id_for_chunker(default_config().chunker_id)
    leftover = application.indexing.vector_store.list_chunk_ids(
        collection_name_for(index_id),
        document_id=error_id,
    )
    assert leftover == []
    meta = application.store.get_vector_index(index_id)
    assert meta is not None
    remaining_points = application.indexing.vector_store.count(
        collection_name_for(index_id)
    )
    assert meta.chunk_count == remaining_points


def test_delete_unrelated_document_leaves_other_searchable(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    error_doc = _upload(client, "error_code.md")
    cake_doc = _upload(client, "cake.md")
    client.delete(f"/api/documents/{error_doc['document_id']}")
    assert cake_doc["document_id"] in _hit_ids(
        application, "chocolate cake cocoa", mode="hybrid"
    )


def test_delete_retry_is_idempotent(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    doc = _upload(client, "error_code.md")
    first = client.delete(f"/api/documents/{doc['document_id']}")
    second = client.delete(f"/api/documents/{doc['document_id']}")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["deleted"] is True
    assert second.json()["already_absent"] is True


def test_delete_does_not_remove_source_file(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    doc = _upload(client, "error_code.md")
    record = application.store.get_by_id(doc["document_id"])
    assert record is not None
    source = Path(record.source_path)
    assert source.is_file()
    client.delete(f"/api/documents/{doc['document_id']}")
    assert source.is_file()


def test_vector_cleanup_failure_keeps_document(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    doc = _upload(client, "error_code.md")
    document_id = doc["document_id"]

    class Boom:
        def purge_document(self, requested_id: str) -> PurgeResult:
            return PurgeResult(
                document_id=requested_id,
                status=VectorPurgeStatus.FAILED,
                indexes_failed=1,
                error_message="forced",
            )

    application.indexing._invalidator = Boom()  # noqa: SLF001
    response = client.delete(f"/api/documents/{document_id}")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "vector_cleanup_failed"
    remaining = application.store.get_by_id(document_id)
    assert remaining is not None
    assert document_id in _hit_ids(application, "ERR_CONNECTION_REFUSED", mode="lexical")


def test_reindex_unchanged_skips_rebuild(tmp_path: Path) -> None:
    client = _client_for(_application(tmp_path))
    doc = _upload(client, "error_code.md")
    response = client.post(f"/api/documents/{doc['document_id']}/reindex")
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "unchanged"
    assert response.json()["document"]["document_id"] == doc["document_id"]


def test_reindex_changed_content_replaces_searchable_text(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    doc = _upload(client, "error_code.md")
    document_id = doc["document_id"]
    record = application.store.get_by_id(document_id)
    assert record is not None
    Path(record.source_path).write_text(
        "# Dessert\n\nChocolate cake requires cocoa after the refresh.\n",
        encoding="utf-8",
    )
    response = client.post(f"/api/documents/{document_id}/reindex")
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "updated"
    assert response.json()["document"]["document_id"] == document_id
    assert document_id not in _hit_ids(
        application, "ERR_CONNECTION_REFUSED", mode="lexical"
    )
    assert document_id in _hit_ids(application, "chocolate cake cocoa", mode="lexical")
    assert document_id in _hit_ids(application, "chocolate cake cocoa", mode="dense")


def test_source_missing_blocks_reindex_but_allows_delete(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    doc = _upload(client, "error_code.md")
    document_id = doc["document_id"]
    record = application.store.get_by_id(document_id)
    assert record is not None
    Path(record.source_path).unlink()
    detail = client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200
    assert detail.json()["source_available"] is False
    listed = client.get("/api/documents").json()["documents"][0]
    assert listed["source_available"] is False
    reindex = client.post(f"/api/documents/{document_id}/reindex")
    assert reindex.status_code == 409
    assert reindex.json()["error"]["code"] == "source_missing"
    deleted = client.delete(f"/api/documents/{document_id}")
    assert deleted.status_code == 200
    assert application.store.get_by_id(document_id) is None


def test_delete_unknown_id_is_already_absent(tmp_path: Path) -> None:
    client = _client_for(_application(tmp_path))
    response = client.delete("/api/documents/" + "a" * 64)
    assert response.status_code == 200
    assert response.json()["already_absent"] is True
    assert response.json()["deleted"] is True


def test_sqlite_delete_cascades_chunks(tmp_path: Path) -> None:
    application = _application(tmp_path)
    library = DocumentLibrary(application)
    path = tmp_path / "note.md"
    path.write_text("# Note\n\nERR_CONNECTION_REFUSED appears here.\n", encoding="utf-8")
    prepared = library.ingest_and_index(path)
    document_id = prepared.summary.document_id
    assert application.store.count_chunks(document_id) >= 1
    assert application.store.delete_document(document_id) is True
    assert application.store.get_by_id(document_id) is None
    assert application.store.count_chunks(document_id) == 0
    assert path.is_file()


def test_document_list_orders_recent_updates_first(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    cake = _upload(client, "cake.md")
    error = _upload(client, "error_code.md")
    with application.store._connect() as conn:  # noqa: SLF001
        conn.execute(
            "UPDATE documents SET updated_at = ? WHERE document_id = ?",
            ("2026-01-01 00:00:00", cake["document_id"]),
        )
        conn.execute(
            "UPDATE documents SET updated_at = ? WHERE document_id = ?",
            ("2026-01-02 00:00:00", error["document_id"]),
        )
        conn.commit()
    names = [item["filename"] for item in client.get("/api/documents").json()["documents"]]
    assert names[0] == error["filename"]
    record = application.store.get_by_id(cake["document_id"])
    assert record is not None
    Path(record.source_path).write_text(
        "# Dessert\n\nChocolate cake requires cocoa after the refresh.\n",
        encoding="utf-8",
    )
    reindexed = client.post(f"/api/documents/{cake['document_id']}/reindex")
    assert reindexed.status_code == 200, reindexed.text
    names = [item["filename"] for item in client.get("/api/documents").json()["documents"]]
    assert names[0] == cake["filename"]


def test_failing_qdrant_delete_does_not_drop_sqlite(tmp_path: Path) -> None:
    inner = _application(tmp_path)
    library = DocumentLibrary(inner)
    path = tmp_path / "note.md"
    path.write_text("# Note\n\nERR_CONNECTION_REFUSED appears here.\n", encoding="utf-8")
    prepared = library.ingest_and_index(path)
    document_id = prepared.summary.document_id

    class FailingStore:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        def delete_by_document(self, *args, **kwargs):
            raise VectorStoreError("forced", code="vector_store_error")

        def __getattr__(self, name):
            return getattr(self._wrapped, name)

    inner.indexing._invalidator._vector_store = FailingStore(  # noqa: SLF001
        inner.indexing.vector_store
    )
    from research_assistant.api.errors import ApiError

    try:
        library.delete_document(document_id)
        raise AssertionError("expected vector cleanup failure")
    except ApiError as exc:
        assert exc.code == "vector_cleanup_failed"
    assert inner.store.get_by_id(document_id) is not None


def test_details_returns_parser_warning_strings(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    uploaded = client.post(
        "/api/documents",
        files={
            "file": (
                "warn.md",
                b"# Title\n\n```python\nprint(1)\n",
                "text/markdown",
            )
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    document_id = body["document"]["document_id"]
    assert "unclosed_code_fence" in body["warnings"]
    detail = client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["filename"] == "warn.md"
    assert payload["status"] == "ready"
    assert payload["chunk_count"] >= 1
    assert "unclosed_code_fence" in payload["warnings"]
    assert payload["warning_count"] >= 1


def test_reindex_with_parser_warnings_keeps_document_id(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    uploaded = client.post(
        "/api/documents",
        files={
            "file": (
                "warn.md",
                b"# Title\n\n```python\nprint(1)\n",
                "text/markdown",
            )
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["document"]["document_id"]
    record = application.store.get_by_id(document_id)
    assert record is not None
    Path(record.source_path).write_text(
        "# Title\n\n```python\nprint(2)\n",
        encoding="utf-8",
    )
    reindexed = client.post(f"/api/documents/{document_id}/reindex")
    assert reindexed.status_code == 200, reindexed.text
    assert reindexed.json()["document"]["document_id"] == document_id
    assert reindexed.json()["document"]["status"] == "ready"
    assert "unclosed_code_fence" in reindexed.json()["warnings"]
    detail = client.get(f"/api/documents/{document_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["document_id"] == document_id


def test_details_survives_unreadable_parsed_payload(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    doc = _upload(client, "cake.md")
    with application.store._connect() as conn:  # noqa: SLF001
        conn.execute(
            "UPDATE documents SET parsed_json = ? WHERE document_id = ?",
            ("{not-json", doc["document_id"]),
        )
        conn.commit()
    detail = client.get(f"/api/documents/{doc['document_id']}")
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["filename"] == "cake.md"
    assert payload["warnings"] == []
    assert payload["chunk_count"] >= 1


def test_details_available_after_new_api_client(tmp_path: Path) -> None:
    application = _application(tmp_path)
    client = _client_for(application)
    doc = _upload(client, "cake.md")
    restarted = _client_for(application)
    detail = restarted.get(f"/api/documents/{doc['document_id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["filename"] == "cake.md"
    assert detail.json()["document_id"] == doc["document_id"]
