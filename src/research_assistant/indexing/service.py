"""Index chunks into a VectorStore. Embedding and storage stay independent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from research_assistant.chunking.models import Chunk
from research_assistant.core.errors import VectorStoreError
from research_assistant.core.logging import get_logger
from research_assistant.core.resource import (
    RESOURCE_EXHAUSTED_CODE,
    looks_like_resource_exhaustion,
    sanitize_public_error,
)
from research_assistant.core.settings import Settings, load_settings
from research_assistant.core.timing import Timer
from research_assistant.core.types import IndexingOutcome, IndexStatus
from research_assistant.embeddings.factory import embedding_model_from_settings
from research_assistant.embeddings.identity import EmbeddingIdentity
from research_assistant.embeddings.protocol import EmbeddingModel
from research_assistant.indexing.identity import (
    VECTOR_SCHEMA_VERSION,
    collection_name_for,
    index_id_for,
)
from research_assistant.indexing.invalidation import (
    PurgeResult,
    RegistryVectorInvalidator,
)
from research_assistant.indexing.models import VectorPayload, VectorRecord
from research_assistant.indexing.protocol import VectorStore
from research_assistant.indexing.qdrant_store import qdrant_store_for
from research_assistant.storage.records import DocumentRecord, IndexMetadata
from research_assistant.storage.sqlite import SqliteDocumentStore

logger = get_logger("research_assistant.indexing")


@dataclass(frozen=True)
class IndexingResult:
    outcome: IndexingOutcome
    index_id: str
    chunker_id: str
    embedding_model_id: str
    indexed_count: int
    skipped_empty: int
    warnings: tuple[str, ...] = ()
    error_type: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome is not IndexingOutcome.FAILED


class IndexingService:
    def __init__(
        self,
        settings: Settings | None = None,
        store: SqliteDocumentStore | None = None,
        embedder: EmbeddingModel | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._store = store or SqliteDocumentStore(self._settings.database_path)
        self._embedder = embedder
        self._vectors = vector_store or qdrant_store_for(self._settings.vector_index_path)
        self._invalidator = RegistryVectorInvalidator(self._store, self._vectors)

    @property
    def vector_store(self) -> VectorStore:
        return self._vectors

    @property
    def embedder(self) -> EmbeddingModel:
        if self._embedder is None:
            self._embedder = embedding_model_from_settings(self._settings)
        return self._embedder

    @property
    def embedding(self) -> EmbeddingIdentity:
        return self.embedder.identity

    def index_id_for_chunker(self, chunker_id: str) -> str:
        return index_id_for(
            embedding=self.embedder.identity,
            chunker_id=chunker_id,
        )

    def index_document(
        self, document_id: str, chunker_id: str
    ) -> IndexingResult:
        chunks = self._store.list_chunks(document_id, chunker_id)
        record = self._store.get_by_id(document_id)
        filename = record.filename if record is not None else ""
        return self._index_chunks(
            chunks,
            chunker_id=chunker_id,
            filename_by_document={document_id: filename},
            replace_documents=(document_id,),
        )

    def index_chunker(self, chunker_id: str) -> IndexingResult:
        chunks = self._store.list_chunks_for_chunker(chunker_id)
        filenames = {
            doc.document_id: doc.filename
            for doc in self._documents_for(chunks)
        }
        return self._index_chunks(
            chunks,
            chunker_id=chunker_id,
            filename_by_document=filenames,
            replace_documents=None,
            rebuild=True,
        )

    def purge_document(self, document_id: str) -> PurgeResult:
        """Remove vectors for a document from every registered index."""
        return self._invalidator.purge_document(document_id)

    def _index_chunks(
        self,
        chunks: list[Chunk],
        *,
        chunker_id: str,
        filename_by_document: dict[str, str],
        replace_documents: tuple[str, ...] | None,
        rebuild: bool = False,
    ) -> IndexingResult:
        identity = self.embedder.identity
        index_id = index_id_for(embedding=identity, chunker_id=chunker_id)
        collection = collection_name_for(index_id)
        logger.info(
            "indexing_started index_id=%s chunker_id=%s chunks=%s",
            index_id,
            chunker_id,
            len(chunks),
        )
        try:
            self._vectors.ensure_collection(
                collection_name=collection,
                dimension=identity.dimension,
                metric=identity.metric,
            )
        except VectorStoreError as exc:
            return _failed(index_id, chunker_id, identity, exc)

        now = _utc_now()
        existing = self._store.get_vector_index(index_id)
        if existing is not None and _incompatible(existing, identity, chunker_id):
            return IndexingResult(
                outcome=IndexingOutcome.FAILED,
                index_id=index_id,
                chunker_id=chunker_id,
                embedding_model_id=identity.embedding_model_id,
                indexed_count=0,
                skipped_empty=0,
                error_type="incompatible_index",
                error_message=(
                    "Existing index metadata does not match embedding/chunker config"
                ),
            )
        self._store.upsert_vector_index(
            IndexMetadata(
                index_id=index_id,
                collection_name=collection,
                embedding_model_id=identity.embedding_model_id,
                chunker_id=chunker_id,
                dimension=identity.dimension,
                metric=identity.metric,
                normalized=identity.normalize,
                schema_version=VECTOR_SCHEMA_VERSION,
                backend=getattr(self._vectors, "backend_name", "qdrant-local"),
                status=IndexStatus.BUILDING,
                chunk_count=existing.chunk_count if existing else 0,
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
        )

        usable = [chunk for chunk in chunks if chunk.text.strip()]
        skipped = len(chunks) - len(usable)
        warnings = []
        if skipped:
            warnings.append(f"skipped_empty:{skipped}")

        try:
            if rebuild:
                stale = self._vectors.list_chunk_ids(collection)
                self._vectors.delete_ids(collection, stale)
            elif replace_documents:
                for document_id in replace_documents:
                    self._vectors.delete_by_document(
                        collection, document_id, chunker_id
                    )

            if not usable:
                count = self._vectors.count(collection)
                self._store.upsert_vector_index(
                    IndexMetadata(
                        index_id=index_id,
                        collection_name=collection,
                        embedding_model_id=identity.embedding_model_id,
                        chunker_id=chunker_id,
                        dimension=identity.dimension,
                        metric=identity.metric,
                        normalized=identity.normalize,
                        schema_version=VECTOR_SCHEMA_VERSION,
                        backend=getattr(self._vectors, "backend_name", "qdrant-local"),
                        status=IndexStatus.READY,
                        chunk_count=count,
                        created_at=existing.created_at if existing else now,
                        updated_at=_utc_now(),
                    )
                )
                return IndexingResult(
                    outcome=IndexingOutcome.EMPTY,
                    index_id=index_id,
                    chunker_id=chunker_id,
                    embedding_model_id=identity.embedding_model_id,
                    indexed_count=0,
                    skipped_empty=skipped,
                    warnings=tuple(warnings),
                )

            batch_size = max(1, self._settings.embedding_batch_size)
            with Timer("embed_index") as timer:
                for start in range(0, len(usable), batch_size):
                    batch = usable[start : start + batch_size]
                    vectors = self.embedder.embed_documents(
                        [chunk.text for chunk in batch]
                    )
                    records = [
                        VectorRecord(
                            chunk_id=chunk.chunk_id,
                            vector=vector,
                            payload=_payload(
                                chunk,
                                filename_by_document.get(chunk.document_id, ""),
                            ),
                        )
                        for chunk, vector in zip(batch, vectors, strict=True)
                    ]
                    self._vectors.upsert(collection, records)
            count = self._vectors.count(collection)
            self._store.upsert_vector_index(
                IndexMetadata(
                    index_id=index_id,
                    collection_name=collection,
                    embedding_model_id=identity.embedding_model_id,
                    chunker_id=chunker_id,
                    dimension=identity.dimension,
                    metric=identity.metric,
                    normalized=identity.normalize,
                    schema_version=VECTOR_SCHEMA_VERSION,
                    backend=getattr(self._vectors, "backend_name", "qdrant-local"),
                    status=IndexStatus.READY,
                    chunk_count=count,
                    created_at=existing.created_at if existing else now,
                    updated_at=_utc_now(),
                )
            )
            outcome = (
                IndexingOutcome.UPDATED if existing else IndexingOutcome.CREATED
            )
            logger.info(
                "indexing_completed index_id=%s outcome=%s indexed=%s "
                "skipped_empty=%s embed_ms=%.1f",
                index_id,
                outcome.value,
                len(usable),
                skipped,
                timer.seconds * 1000,
            )
            return IndexingResult(
                outcome=outcome,
                index_id=index_id,
                chunker_id=chunker_id,
                embedding_model_id=identity.embedding_model_id,
                indexed_count=len(usable),
                skipped_empty=skipped,
                warnings=tuple(warnings),
            )
        except Exception as exc:
            logger.exception("indexing_failed index_id=%s", index_id)
            public = sanitize_public_error(str(getattr(exc, "message", exc)))
            self._store.mark_vector_index_failed(index_id, public)
            return _failed(index_id, chunker_id, identity, exc)

    def _documents_for(self, chunks: list[Chunk]) -> list[DocumentRecord]:
        seen: dict[str, DocumentRecord] = {}
        for chunk in chunks:
            if chunk.document_id in seen:
                continue
            record = self._store.get_by_id(chunk.document_id)
            if record is not None:
                seen[chunk.document_id] = record
        return list(seen.values())


def _payload(chunk: Chunk, filename: str) -> VectorPayload:
    return VectorPayload(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        chunker_id=chunk.chunker_id,
        position=chunk.position,
        content_hash=chunk.content_hash,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        section_path=chunk.section_path,
        filename=filename,
        char_count=chunk.char_count,
    )


def _incompatible(
    existing: IndexMetadata, identity: EmbeddingIdentity, chunker_id: str
) -> bool:
    return (
        existing.embedding_model_id != identity.embedding_model_id
        or existing.chunker_id != chunker_id
        or existing.dimension != identity.dimension
        or existing.metric != identity.metric
        or existing.normalized != identity.normalize
        or existing.schema_version != VECTOR_SCHEMA_VERSION
    )


def _failed(
    index_id: str,
    chunker_id: str,
    identity: EmbeddingIdentity,
    exc: BaseException,
) -> IndexingResult:
    if looks_like_resource_exhaustion(exc) or getattr(exc, "code", "") == RESOURCE_EXHAUSTED_CODE:
        code = RESOURCE_EXHAUSTED_CODE
        message = sanitize_public_error(str(getattr(exc, "message", exc)))
    else:
        code = getattr(exc, "code", "indexing_error")
        raw = str(getattr(exc, "message", exc))
        message = sanitize_public_error(raw)
    return IndexingResult(
        outcome=IndexingOutcome.FAILED,
        index_id=index_id,
        chunker_id=chunker_id,
        embedding_model_id=identity.embedding_model_id,
        indexed_count=0,
        skipped_empty=0,
        error_type=str(code),
        error_message=message,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
