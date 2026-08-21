"""Document store protocol."""

from __future__ import annotations

from typing import Protocol

from research_assistant.storage.records import DocumentRecord


class DocumentStore(Protocol):
    def get_by_id(self, document_id: str) -> DocumentRecord | None: ...

    def get_by_source_path(self, source_path: str) -> DocumentRecord | None: ...

    def upsert(self, record: DocumentRecord) -> None: ...
