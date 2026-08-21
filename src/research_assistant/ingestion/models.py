"""Ingestion result types."""

from __future__ import annotations

from dataclasses import dataclass

from research_assistant.core.types import IngestOutcome, ParseStatus, VectorPurgeStatus
from research_assistant.parsing.models import ParsedDocument
from research_assistant.storage.records import DocumentRecord


@dataclass(frozen=True)
class IngestResult:
    outcome: IngestOutcome
    source_path: str
    document: DocumentRecord | None
    parsed: ParsedDocument | None = None
    error_type: str | None = None
    error_message: str | None = None
    vector_purge_status: VectorPurgeStatus = VectorPurgeStatus.NOT_APPLICABLE
    vector_purge_error: str | None = None
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return (
            self.document is not None
            and self.document.parse_status is ParseStatus.PARSED
        )
