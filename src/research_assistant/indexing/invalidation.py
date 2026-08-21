"""Stale-vector invalidation. Ingestion depends on this protocol, not Qdrant."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from research_assistant.core.errors import VectorStoreError
from research_assistant.core.logging import get_logger
from research_assistant.core.types import VectorPurgeStatus
from research_assistant.indexing.protocol import VectorStore
from research_assistant.storage.records import IndexMetadata

logger = get_logger("research_assistant.indexing.invalidation")


class IndexRegistry(Protocol):
    def list_vector_indexes(self) -> list[IndexMetadata]: ...

    def update_vector_index_count(self, index_id: str, chunk_count: int) -> None: ...


@dataclass(frozen=True)
class PurgeResult:
    document_id: str
    status: VectorPurgeStatus
    indexes_seen: int = 0
    indexes_purged: int = 0
    indexes_missing: int = 0
    indexes_failed: int = 0
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.status is not VectorPurgeStatus.FAILED


class VectorIndexInvalidator(Protocol):
    def purge_document(self, document_id: str) -> PurgeResult: ...


class NullVectorIndexInvalidator:
    """Explicit no-op for tests that isolate ingest from indexing."""

    def purge_document(self, document_id: str) -> PurgeResult:
        return PurgeResult(
            document_id=document_id,
            status=VectorPurgeStatus.NOOP,
        )


class RegistryVectorInvalidator:
    """Delete a document's points from every registered vector index.

    Missing collections are skipped. Per-index backend errors are recorded;
    other indexes still get a best-effort purge. Safe to call repeatedly.
    """

    def __init__(
        self,
        registry: IndexRegistry,
        vector_store: VectorStore | None = None,
        *,
        vector_store_factory: Callable[[], VectorStore] | None = None,
    ) -> None:
        self._registry = registry
        self._vector_store = vector_store
        self._factory = vector_store_factory

    def purge_document(self, document_id: str) -> PurgeResult:
        indexes = self._registry.list_vector_indexes()
        if not indexes:
            return PurgeResult(
                document_id=document_id,
                status=VectorPurgeStatus.NOOP,
            )
        try:
            store = self._store()
        except VectorStoreError as exc:
            logger.info(
                "vector_purge_failed document_id=%s error=%s",
                document_id,
                exc.message,
            )
            return PurgeResult(
                document_id=document_id,
                status=VectorPurgeStatus.FAILED,
                indexes_seen=len(indexes),
                indexes_failed=len(indexes),
                error_message=exc.message,
            )

        purged = 0
        missing = 0
        failed = 0
        errors: list[str] = []
        for meta in indexes:
            try:
                if not store.collection_exists(meta.collection_name):
                    missing += 1
                    continue
                store.delete_by_document(meta.collection_name, document_id)
                remaining = store.count(meta.collection_name)
                self._registry.update_vector_index_count(meta.index_id, remaining)
                purged += 1
            except VectorStoreError as exc:
                failed += 1
                errors.append(f"{meta.index_id}:{exc.message}")
                logger.info(
                    "vector_purge_index_failed index_id=%s document_id=%s error=%s",
                    meta.index_id,
                    document_id,
                    exc.message,
                )
        status = (
            VectorPurgeStatus.FAILED if failed else VectorPurgeStatus.PURGED
        )
        return PurgeResult(
            document_id=document_id,
            status=status,
            indexes_seen=len(indexes),
            indexes_purged=purged,
            indexes_missing=missing,
            indexes_failed=failed,
            error_message="; ".join(errors) if errors else None,
        )

    def _store(self) -> VectorStore:
        if self._vector_store is None:
            if self._factory is None:
                raise VectorStoreError(
                    "No vector store configured for invalidation",
                    code="vector_store_unavailable",
                )
            self._vector_store = self._factory()
        return self._vector_store


def default_vector_invalidator(
    registry: object,
    *,
    vector_store: VectorStore | None = None,
    vector_index_path: Path | None = None,
) -> VectorIndexInvalidator:
    list_indexes = getattr(registry, "list_vector_indexes", None)
    if not callable(list_indexes):
        return NullVectorIndexInvalidator()
    factory = None
    if vector_store is None and vector_index_path is not None:
        path = vector_index_path

        def factory() -> VectorStore:
            from research_assistant.indexing.qdrant_store import qdrant_store_for

            return qdrant_store_for(path)

    return RegistryVectorInvalidator(
        registry,  # type: ignore[arg-type]
        vector_store=vector_store,
        vector_store_factory=factory,
    )
