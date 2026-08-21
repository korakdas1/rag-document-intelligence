"""Qdrant VectorStore. Local embedded mode by default; no Docker required."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from research_assistant.core.errors import VectorStoreError
from research_assistant.indexing.models import VectorHit, VectorPayload, VectorRecord
from research_assistant.indexing.point_ids import point_id_for

_METRIC_MAP = {
    "cosine": "Cosine",
    "dot": "Dot",
    "euclidean": "Euclid",
}


class QdrantVectorStore:
    backend_name = "qdrant-local"

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path).expanduser().resolve()
        self._path.mkdir(parents=True, exist_ok=True)
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise VectorStoreError(
                "qdrant-client is required for the default vector backend",
                code="missing_dependency",
            ) from exc
        try:
            self._client = QdrantClient(path=str(self._path))
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(
                f"Qdrant local store unavailable at {self._path}: {exc}",
                code="vector_store_unavailable",
            ) from exc

    def ensure_collection(
        self, *, collection_name: str, dimension: int, metric: str
    ) -> None:
        from qdrant_client.models import Distance, VectorParams

        distance = _METRIC_MAP.get(metric)
        if distance is None:
            raise VectorStoreError(
                f"Unsupported metric {metric!r}",
                code="unsupported_metric",
            )
        if self.collection_exists(collection_name):
            existing = self.collection_dimension(collection_name)
            if existing != dimension:
                raise VectorStoreError(
                    f"Collection {collection_name} has dimension {existing}, "
                    f"expected {dimension}",
                    code="dimension_mismatch",
                )
            return
        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=dimension,
                distance=Distance(distance),
            ),
        )

    def collection_exists(self, collection_name: str) -> bool:
        try:
            return bool(self._client.collection_exists(collection_name))
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError(
                f"Failed to inspect collection {collection_name}: {exc}",
                code="vector_store_unavailable",
            ) from exc

    def collection_dimension(self, collection_name: str) -> int:
        if not self.collection_exists(collection_name):
            raise VectorStoreError(
                f"Collection {collection_name} does not exist",
                code="missing_index",
            )
        info = self._client.get_collection(collection_name)
        params = info.config.params.vectors
        size = getattr(params, "size", None)
        if size is None:
            raise VectorStoreError(
                f"Collection {collection_name} has no dense vector size",
                code="dimension_mismatch",
            )
        return int(size)

    def upsert(self, collection_name: str, records: Sequence[VectorRecord]) -> None:
        if not records:
            return
        from qdrant_client.models import PointStruct

        expected = self.collection_dimension(collection_name)
        points = []
        for record in records:
            if len(record.vector) != expected:
                raise VectorStoreError(
                    f"Vector dim {len(record.vector)} != collection {expected}",
                    code="dimension_mismatch",
                )
            points.append(
                PointStruct(
                    id=point_id_for(record.chunk_id),
                    vector=list(record.vector),
                    payload=record.payload.to_dict(),
                )
            )
        self._client.upsert(collection_name=collection_name, points=points)

    def delete_ids(self, collection_name: str, chunk_ids: Sequence[str]) -> None:
        if not chunk_ids:
            return
        ids = [point_id_for(chunk_id) for chunk_id in chunk_ids]
        self._client.delete(collection_name=collection_name, points_selector=ids)

    def delete_by_document(
        self,
        collection_name: str,
        document_id: str,
        chunker_id: str | None = None,
    ) -> None:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        must = [
            FieldCondition(key="document_id", match=MatchValue(value=document_id)),
        ]
        if chunker_id is not None:
            must.append(
                FieldCondition(key="chunker_id", match=MatchValue(value=chunker_id))
            )
        self._client.delete(
            collection_name=collection_name,
            points_selector=Filter(must=must),
        )

    def search(
        self,
        collection_name: str,
        query_vector: Sequence[float],
        *,
        top_k: int,
        payload_filter: object | None = None,
    ) -> list[VectorHit]:
        if not self.collection_exists(collection_name):
            raise VectorStoreError(
                f"Collection {collection_name} does not exist",
                code="missing_index",
            )
        if top_k < 1:
            raise VectorStoreError("top_k must be >= 1", code="invalid_top_k")
        expected = self.collection_dimension(collection_name)
        if len(query_vector) != expected:
            raise VectorStoreError(
                f"Query dim {len(query_vector)} != collection {expected}",
                code="dimension_mismatch",
            )
        query_filter = _qdrant_filter(payload_filter)
        response = self._client.query_points(
            collection_name=collection_name,
            query=list(query_vector),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        hits: list[VectorHit] = []
        for item in response.points:
            payload = VectorPayload.from_dict(dict(item.payload or {}))
            hits.append(
                VectorHit(
                    chunk_id=payload.chunk_id,
                    score=float(item.score),
                    payload=payload,
                )
            )
        return hits

    def count(self, collection_name: str) -> int:
        if not self.collection_exists(collection_name):
            return 0
        result = self._client.count(collection_name=collection_name, exact=True)
        return int(result.count)

    def get_payload(
        self, collection_name: str, chunk_id: str
    ) -> dict[str, object] | None:
        points = self._client.retrieve(
            collection_name=collection_name,
            ids=[point_id_for(chunk_id)],
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            return None
        return dict(points[0].payload or {})

    def list_chunk_ids(
        self,
        collection_name: str,
        *,
        document_id: str | None = None,
        chunker_id: str | None = None,
    ) -> list[str]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        if not self.collection_exists(collection_name):
            return []
        must = []
        if document_id is not None:
            must.append(
                FieldCondition(key="document_id", match=MatchValue(value=document_id))
            )
        if chunker_id is not None:
            must.append(
                FieldCondition(key="chunker_id", match=MatchValue(value=chunker_id))
            )
        query_filter = Filter(must=must) if must else None
        ids: list[str] = []
        offset = None
        while True:
            records, offset = self._client.scroll(
                collection_name=collection_name,
                scroll_filter=query_filter,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                payload = record.payload or {}
                chunk_id = payload.get("chunk_id")
                if chunk_id:
                    ids.append(str(chunk_id))
            if offset is None:
                break
        return ids

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()
        _STORE_CACHE.pop(str(self._path.resolve()), None)


_STORE_CACHE: dict[str, QdrantVectorStore] = {}


def qdrant_store_for(path: Path | str) -> QdrantVectorStore:
    """Reuse one local client per path so ingest and indexing share a lock."""
    key = str(Path(path).expanduser().resolve())
    store = _STORE_CACHE.get(key)
    if store is None:
        store = QdrantVectorStore(key)
        _STORE_CACHE[key] = store
    return store


def _qdrant_filter(payload_filter: object | None):
    if payload_filter is None or not getattr(payload_filter, "active", False):
        return None
    from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, Range

    must = []
    document_ids = tuple(getattr(payload_filter, "document_ids", ()) or ())
    filenames = tuple(getattr(payload_filter, "filenames", ()) or ())
    page = getattr(payload_filter, "page", None)
    section_prefix = tuple(getattr(payload_filter, "section_prefix", ()) or ())
    if document_ids:
        must.append(
            FieldCondition(
                key="document_id",
                match=MatchAny(any=list(document_ids)),
            )
        )
    if filenames:
        must.append(
            FieldCondition(
                key="filename",
                match=MatchAny(any=list(filenames)),
            )
        )
    if page is not None:
        must.append(FieldCondition(key="page_start", range=Range(lte=page)))
        must.append(FieldCondition(key="page_end", range=Range(gte=page)))
    if section_prefix:
        key = "\x1f".join(section_prefix)
        must.append(
            FieldCondition(key="section_prefixes", match=MatchValue(value=key))
        )
    return Filter(must=must) if must else None

