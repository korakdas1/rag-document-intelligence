"""One readiness rule for document views, repair, and every retrieval mode."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from research_assistant.chunking.models import Chunk
from research_assistant.core.logging import get_logger
from research_assistant.core.types import ParseStatus
from research_assistant.embeddings.identity import EmbeddingIdentity
from research_assistant.indexing.identity import (
    VECTOR_SCHEMA_VERSION,
    collection_name_for,
    index_id_for,
)
from research_assistant.indexing.models import VectorPayload
from research_assistant.indexing.protocol import VectorStore
from research_assistant.storage.sqlite import SqliteDocumentStore

logger = get_logger("research_assistant.indexing.health")


def representation_matches(
    expected: Mapping[str, Chunk], actual: Sequence[VectorPayload]
) -> bool:
    """Match identities and provenance, including equal-count stale replacements."""
    return (
        len(actual) == len(expected)
        and {point.chunk_id for point in actual} == set(expected)
        and all(
            point.document_id == expected[point.chunk_id].document_id
            and point.chunker_id == expected[point.chunk_id].chunker_id
            and point.content_hash == expected[point.chunk_id].content_hash
            for point in actual
        )
    )


@dataclass(frozen=True)
class DocumentIndexHealth:
    document_id: str
    index_id: str
    status: str
    expected_ids: frozenset[str]
    actual_ids: frozenset[str]

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    @property
    def missing_ids(self) -> frozenset[str]:
        return self.expected_ids - self.actual_ids

    @property
    def stale_ids(self) -> frozenset[str]:
        return self.actual_ids - self.expected_ids

    @property
    def message(self) -> str | None:
        if self.ready or self.status == "not_indexed":
            return None
        if self.status == "building":
            return "Indexing has not completed. Re-index if the operation was interrupted."
        return "Document index is incomplete or unavailable. Re-index to repair it."


class DocumentIndexHealthService:
    def __init__(
        self,
        store: SqliteDocumentStore,
        vectors: VectorStore,
        embedding: Callable[[], EmbeddingIdentity],
    ) -> None:
        self._store = store
        self._vectors = vectors
        self._embedding = embedding

    def document_index_health(
        self, document_id: str, chunker_id: str
    ) -> DocumentIndexHealth:
        return self.inspect(chunker_id, document_id=document_id)[document_id]

    def inspect(
        self, chunker_id: str, *, document_id: str | None = None
    ) -> dict[str, DocumentIndexHealth]:
        """Batch library checks into one vector inventory, or inspect one document.

        This is a point-in-time reconciliation, not a cross-store transaction.
        No health cache may hide vector deletion or a failed activation.
        """
        if document_id is None:
            documents = {doc.document_id: doc for doc in self._store.list_documents()}
            chunks = self._store.list_chunks_for_chunker(chunker_id)
        else:
            documents = {document_id: self._store.get_by_id(document_id)}
            chunks = self._store.list_chunks(document_id, chunker_id)
        expected: dict[str, dict[str, Chunk]] = {doc_id: {} for doc_id in documents}
        for chunk in chunks:
            if chunk.text.strip() and chunk.document_id in expected:
                expected[chunk.document_id][chunk.chunk_id] = chunk
        if not documents:
            return {}
        index_id = ""
        try:
            identity = self._embedding()
            index_id = index_id_for(embedding=identity, chunker_id=chunker_id)
            collection = collection_name_for(index_id)
            meta = self._store.get_vector_index(index_id)
            states = self._store.list_document_indexes(index_id, document_id=document_id)
            compatible = bool(
                meta
                and meta.collection_name == collection
                and meta.embedding_model_id == identity.embedding_model_id
                and meta.chunker_id == chunker_id
                and meta.dimension == identity.dimension
                and meta.metric == identity.metric
                and meta.normalized == identity.normalize
                and meta.schema_version == VECTOR_SCHEMA_VERSION
                and self._vectors.collection_exists(collection)
                and self._vectors.collection_dimension(collection) == identity.dimension
            )
            payloads = (
                self._vectors.list_payloads(collection, document_id=document_id)
                if compatible else []
            )
        except Exception:
            # Public document views remain available; no raw backend error is exposed.
            logger.exception("document_index_inspection_failed chunker_id=%s", chunker_id)
            return {
                doc_id: DocumentIndexHealth(
                    doc_id, index_id, "unavailable", frozenset(rows), frozenset()
                )
                for doc_id, rows in expected.items()
            }

        actual: dict[str, list[VectorPayload]] = {}
        for payload in payloads:
            actual.setdefault(payload.document_id, []).append(payload)
        result: dict[str, DocumentIndexHealth] = {}
        for doc_id, rows in expected.items():
            doc = documents[doc_id]
            state = states.get(doc_id)
            points = actual.get(doc_id, [])
            expected_ids = frozenset(rows)
            actual_ids = frozenset(point.chunk_id for point in points)
            valid = bool(
                compatible
                and doc and doc.parse_status is ParseStatus.PARSED
                and expected_ids and representation_matches(rows, points)
                and state and state.status in {"ready", "unverified"}
                and state.source_checksum == doc.checksum_sha256
                and state.chunk_ids == expected_ids
            )
            if valid:
                status = "ready"
            elif state and state.status in {"building", "failed"}:
                status = state.status
            elif not expected_ids and not points:
                status = "not_indexed"
            else:
                status = "repair_required"
            result[doc_id] = DocumentIndexHealth(
                doc_id, index_id, status, expected_ids, actual_ids
            )
        return result

    def searchable_document_ids(self, chunker_id: str) -> frozenset[str]:
        return frozenset(
            doc_id for doc_id, health in self.inspect(chunker_id).items() if health.ready
        )
