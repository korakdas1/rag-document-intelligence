"""VectorStore protocol. Implementations must not embed text or know SQLite."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from research_assistant.indexing.models import VectorHit, VectorRecord


class VectorStore(Protocol):
    def ensure_collection(
        self,
        *,
        collection_name: str,
        dimension: int,
        metric: str,
    ) -> None: ...

    def collection_exists(self, collection_name: str) -> bool: ...

    def collection_dimension(self, collection_name: str) -> int: ...

    def upsert(
        self, collection_name: str, records: Sequence[VectorRecord]
    ) -> None: ...

    def delete_ids(self, collection_name: str, chunk_ids: Sequence[str]) -> None: ...

    def delete_by_document(
        self,
        collection_name: str,
        document_id: str,
        chunker_id: str | None = None,
    ) -> None: ...

    def search(
        self,
        collection_name: str,
        query_vector: Sequence[float],
        *,
        top_k: int,
        payload_filter: object | None = None,
    ) -> list[VectorHit]: ...

    def count(self, collection_name: str) -> int: ...

    def get_payload(
        self, collection_name: str, chunk_id: str
    ) -> dict[str, object] | None: ...

    def list_chunk_ids(
        self,
        collection_name: str,
        *,
        document_id: str | None = None,
        chunker_id: str | None = None,
    ) -> list[str]: ...

    def close(self) -> None: ...
