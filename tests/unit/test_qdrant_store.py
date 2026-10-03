from pathlib import Path

import pytest

from research_assistant.core.errors import VectorStoreError
from research_assistant.indexing.models import VectorPayload, VectorRecord
from research_assistant.indexing.qdrant_store import QdrantVectorStore


def _payload(chunk_id: str, document_id: str = "doc-a") -> VectorPayload:
    return VectorPayload(
        chunk_id=chunk_id,
        document_id=document_id,
        chunker_id="structure.v1:test",
        position=0,
        content_hash="abc",
        page_start=1,
        page_end=2,
        section_path=("Methods",),
        filename="paper.md",
        char_count=12,
    )


def _record(chunk_id: str, vector: list[float], document_id: str = "doc-a") -> VectorRecord:
    return VectorRecord(
        chunk_id=chunk_id,
        vector=vector,
        payload=_payload(chunk_id, document_id),
    )


def test_upsert_maps_to_chunk_ids_and_payload(tmp_path: Path) -> None:
    store = QdrantVectorStore(tmp_path / "qdrant")
    store.ensure_collection(collection_name="idx_test", dimension=4, metric="cosine")
    store.upsert(
        "idx_test",
        [_record("chunk-1", [1.0, 0.0, 0.0, 0.0])],
    )
    payload = store.get_payload("idx_test", "chunk-1")
    assert payload is not None
    assert payload["chunk_id"] == "chunk-1"
    assert payload["page_start"] == 1
    assert payload["page_end"] == 2
    assert payload["section_path"] == ["Methods"]
    assert payload["document_id"] == "doc-a"
    store.close()


def test_idempotent_upsert_does_not_duplicate(tmp_path: Path) -> None:
    store = QdrantVectorStore(tmp_path / "qdrant")
    store.ensure_collection(collection_name="idx_test", dimension=4, metric="cosine")
    rec = _record("chunk-1", [1.0, 0.0, 0.0, 0.0])
    store.upsert("idx_test", [rec])
    store.upsert("idx_test", [rec])
    assert store.count("idx_test") == 1
    store.close()


def test_stale_ids_are_deleted(tmp_path: Path) -> None:
    store = QdrantVectorStore(tmp_path / "qdrant")
    store.ensure_collection(collection_name="idx_test", dimension=4, metric="cosine")
    store.upsert(
        "idx_test",
        [
            _record("keep", [1.0, 0.0, 0.0, 0.0]),
            _record("drop", [0.0, 1.0, 0.0, 0.0]),
        ],
    )
    store.delete_ids("idx_test", ["drop"])
    assert store.list_chunk_ids("idx_test") == ["keep"]
    store.close()


def test_dimension_mismatch_fails_clearly(tmp_path: Path) -> None:
    store = QdrantVectorStore(tmp_path / "qdrant")
    store.ensure_collection(collection_name="idx_test", dimension=4, metric="cosine")
    with pytest.raises(VectorStoreError) as exc:
        store.ensure_collection(
            collection_name="idx_test", dimension=8, metric="cosine"
        )
    assert exc.value.code == "dimension_mismatch"
    with pytest.raises(VectorStoreError) as exc2:
        store.upsert("idx_test", [_record("chunk-1", [1.0, 0.0])])
    assert exc2.value.code == "dimension_mismatch"
    store.close()


def test_missing_index_search_fails(tmp_path: Path) -> None:
    store = QdrantVectorStore(tmp_path / "qdrant")
    with pytest.raises(VectorStoreError) as exc:
        store.search("missing", [1.0, 0.0, 0.0, 0.0], top_k=3)
    assert exc.value.code == "missing_index"
    store.close()


def test_search_filter_applies_before_limit(tmp_path: Path) -> None:
    from research_assistant.retrieval.filters import RetrievalFilter

    store = QdrantVectorStore(tmp_path / "qdrant")
    store.ensure_collection(collection_name="idx_test", dimension=4, metric="cosine")
    store.upsert(
        "idx_test",
        [
            _record("keep", [1.0, 0.0, 0.0, 0.0], document_id="doc-a"),
            _record("drop", [0.99, 0.01, 0.0, 0.0], document_id="doc-b"),
        ],
    )
    hits = store.search(
        "idx_test",
        [1.0, 0.0, 0.0, 0.0],
        top_k=1,
        payload_filter=RetrievalFilter(document_ids=("doc-a",)),
    )
    assert [hit.chunk_id for hit in hits] == ["keep"]
    store.close()


def test_payload_inventory_is_paginated_and_document_scoped(tmp_path: Path) -> None:
    store = QdrantVectorStore(tmp_path / "qdrant")
    try:
        assert store.list_payloads("missing") == []
        store.ensure_collection(collection_name="inventory", dimension=4, metric="cosine")
        records = [_record(f"chunk-{i}", [1.0, 0.0, 0.0, 0.0],
                           document_id="doc-a" if i < 270 else "doc-b")
                   for i in range(280)]
        store.upsert("inventory", records)
        assert len(store.list_payloads("inventory")) == 280
        actual = store.list_payloads("inventory", document_id="doc-a")
        assert {point.chunk_id for point in actual} == {f"chunk-{i}" for i in range(270)}
    finally:
        store.close()
