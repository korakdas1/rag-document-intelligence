"""RegistryVectorInvalidator does not need Qdrant or the CLI."""

from __future__ import annotations

from research_assistant.core.errors import VectorStoreError
from research_assistant.core.types import IndexStatus, VectorPurgeStatus
from research_assistant.indexing.invalidation import (
    NullVectorIndexInvalidator,
    RegistryVectorInvalidator,
)
from research_assistant.storage.records import IndexMetadata


class _Registry:
    def __init__(self, indexes: list[IndexMetadata] | None = None) -> None:
        self.indexes = list(indexes or [])
        self.counts: dict[str, int] = {}

    def list_vector_indexes(self) -> list[IndexMetadata]:
        return list(self.indexes)

    def update_vector_index_count(self, index_id: str, chunk_count: int) -> None:
        self.counts[index_id] = chunk_count


class _FakeVectorStore:
    def __init__(
        self,
        *,
        collections: set[str] | None = None,
        fail_on: set[str] | None = None,
        counts: dict[str, int] | None = None,
    ) -> None:
        self.collections = set(collections or ())
        self.fail_on = set(fail_on or ())
        self.counts = dict(counts or {})
        self.deleted: list[tuple[str, str]] = []

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def delete_by_document(
        self,
        collection_name: str,
        document_id: str,
        chunker_id: str | None = None,
    ) -> None:
        if collection_name in self.fail_on:
            raise VectorStoreError(
                f"simulated failure for {collection_name}",
                code="vector_store_error",
            )
        self.deleted.append((collection_name, document_id))

    def count(self, collection_name: str) -> int:
        return self.counts.get(collection_name, 0)


def _meta(index_id: str, collection: str) -> IndexMetadata:
    return IndexMetadata(
        index_id=index_id,
        collection_name=collection,
        embedding_model_id="hashing",
        chunker_id=f"chunker-{index_id}",
        dimension=32,
        metric="cosine",
        normalized=True,
        schema_version=1,
        backend="fake",
        status=IndexStatus.READY,
        chunk_count=3,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def test_empty_registry_is_noop() -> None:
    invalidator = RegistryVectorInvalidator(_Registry(), _FakeVectorStore())
    result = invalidator.purge_document("doc-a")
    assert result.status is VectorPurgeStatus.NOOP
    assert result.ok


def test_null_invalidator_is_noop() -> None:
    result = NullVectorIndexInvalidator().purge_document("doc-a")
    assert result.status is VectorPurgeStatus.NOOP


def test_missing_collection_is_not_failure() -> None:
    registry = _Registry([_meta("idx-1", "idx_missing")])
    store = _FakeVectorStore(collections=set())
    invalidator = RegistryVectorInvalidator(registry, store)
    first = invalidator.purge_document("doc-a")
    second = invalidator.purge_document("doc-a")
    assert first.status is VectorPurgeStatus.PURGED
    assert first.indexes_missing == 1
    assert first.indexes_failed == 0
    assert first.ok
    assert second.status is VectorPurgeStatus.PURGED
    assert store.deleted == []


def test_purge_covers_every_registered_index() -> None:
    registry = _Registry(
        [_meta("idx-1", "col-a"), _meta("idx-2", "col-b")],
    )
    store = _FakeVectorStore(collections={"col-a", "col-b"})
    result = RegistryVectorInvalidator(registry, store).purge_document("doc-a")
    assert result.status is VectorPurgeStatus.PURGED
    assert result.indexes_purged == 2
    assert store.deleted == [("col-a", "doc-a"), ("col-b", "doc-a")]


def test_purge_failure_is_explicit_and_continues() -> None:
    registry = _Registry(
        [_meta("idx-ok", "col-ok"), _meta("idx-bad", "col-bad")],
    )
    store = _FakeVectorStore(
        collections={"col-ok", "col-bad"},
        fail_on={"col-bad"},
        counts={"col-ok": 4},
    )
    result = RegistryVectorInvalidator(registry, store).purge_document("doc-a")
    assert result.status is VectorPurgeStatus.FAILED
    assert not result.ok
    assert result.indexes_purged == 1
    assert result.indexes_failed == 1
    assert store.deleted == [("col-ok", "doc-a")]
    assert registry.counts["idx-ok"] == 4
    assert "idx-bad" in (result.error_message or "")


def test_repeated_purge_is_safe() -> None:
    registry = _Registry([_meta("idx-1", "col-a")])
    store = _FakeVectorStore(collections={"col-a"})
    invalidator = RegistryVectorInvalidator(registry, store)
    first = invalidator.purge_document("doc-a")
    second = invalidator.purge_document("doc-a")
    assert first.ok and second.ok
    assert store.deleted == [("col-a", "doc-a"), ("col-a", "doc-a")]
