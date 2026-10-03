"""Document library workflow: ingest → chunk → index using existing services."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from research_assistant.api.errors import ApiError, error_from_domain
from research_assistant.api.mapping import to_document_summary
from research_assistant.api.schemas import DocumentDetail, DocumentSummary
from research_assistant.api.upload import unique_destination
from research_assistant.app import Application
from research_assistant.chunking.config import ChunkingConfig, default_config
from research_assistant.core.errors import IngestionError
from research_assistant.core.logging import get_logger
from research_assistant.core.resource import (
    RESOURCE_EXHAUSTED_CODE,
    looks_like_resource_exhaustion,
    public_resource_message,
)
from research_assistant.core.types import IngestOutcome
from research_assistant.ingestion.models import IngestResult
from research_assistant.parsing.models import ParsedDocument
from research_assistant.storage.records import DocumentRecord

logger = get_logger("research_assistant.api.library")


@dataclass(frozen=True)
class PreparedDocument:
    summary: DocumentSummary
    outcome: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DeleteResult:
    document_id: str
    deleted: bool
    already_absent: bool
    vector_cleanup_status: str


class DocumentLibrary:
    def __init__(
        self,
        application: Application,
        *,
        chunking: ChunkingConfig | None = None,
    ) -> None:
        self._app = application
        self._chunking = chunking or default_config()

    @property
    def chunker_id(self) -> str:
        return self._chunking.chunker_id

    @property
    def max_file_bytes(self) -> int:
        return self._app.settings.max_file_bytes

    def list_documents(self) -> list[DocumentSummary]:
        records = self._app.store.list_documents()
        health = self._app.indexing.health.inspect(self.chunker_id)
        items: list[DocumentSummary] = []
        for record in records:
            document_health = health.get(record.document_id)
            if document_health is None:
                continue  # Removed while taking the health snapshot.
            count = self._app.store.count_chunks(record.document_id, self.chunker_id)
            items.append(
                to_document_summary(
                    record,
                    chunk_count=count,
                    indexed=document_health.ready,
                    index_health=document_health,
                )
            )
        return items

    def get_document(self, document_id: str) -> DocumentDetail:
        record = self._app.store.get_by_id(document_id)
        if record is None:
            raise ApiError(
                code="not_found",
                message="Document not found.",
                status_code=404,
            )
        count = self._app.store.count_chunks(document_id, self.chunker_id)
        health = self._app.indexing.health.document_index_health(document_id, self.chunker_id)
        summary = to_document_summary(
            record, chunk_count=count, indexed=health.ready, index_health=health
        )
        warnings = _document_warnings(_parsed_payload(record))
        return DocumentDetail(
            **summary.model_dump(),
            chunker_id=self.chunker_id,
            parser_id=record.parser_id,
            warnings=warnings,
            checksum_sha256=record.checksum_sha256,
            index_status=health.status,
        )

    def ingest_and_index(self, path: Path) -> PreparedDocument:
        ingested = self._app.ingest.ingest(path)
        return self._finish_prepare(ingested)

    def reindex_document(self, document_id: str) -> PreparedDocument:
        record = self._require_record(document_id)
        source = Path(record.source_path)
        if not source.is_file():
            logger.info("source_missing document_id=%s", document_id)
            raise ApiError(
                code="source_missing",
                message=(
                    "The source file is no longer available. "
                    "The document can still be removed from the library."
                ),
                status_code=409,
            )
        logger.info("document_reindex_started document_id=%s", document_id)
        ingested = self._app.ingest.ingest(source)
        if (
            ingested.ok
            and ingested.document is not None
            and ingested.outcome is IngestOutcome.UNCHANGED
            and self._document_is_ready(document_id)
        ):
            logger.info(
                "document_reindexed document_id=%s outcome=unchanged",
                document_id,
            )
            return self._prepared_from_record(
                ingested.document,
                outcome=ingested.outcome.value,
                extra_warnings=ingested.warnings,
            )
        prepared = self._finish_prepare(ingested)
        logger.info(
            "document_reindexed document_id=%s outcome=%s",
            document_id,
            prepared.outcome,
        )
        return prepared

    def delete_document(self, document_id: str) -> DeleteResult:
        record = self._app.store.get_by_id(document_id)
        purge = self._app.indexing.purge_document(document_id)
        if not purge.ok:
            logger.info(
                "document_delete_failed document_id=%s vector_status=%s error=%s",
                document_id,
                purge.status.value,
                purge.error_message,
            )
            raise ApiError(
                code="vector_cleanup_failed",
                message=(
                    "Could not remove indexed vectors. "
                    "The document was not deleted. Retry."
                ),
                status_code=503,
            )
        if record is None:
            logger.info(
                "document_deleted document_id=%s already_absent=true vector=%s",
                document_id,
                purge.status.value,
            )
            return DeleteResult(
                document_id=document_id,
                deleted=True,
                already_absent=True,
                vector_cleanup_status=purge.status.value,
            )
        self._app.store.delete_document(document_id)
        remaining = self._app.store.get_by_id(document_id)
        leftover_chunks = self._app.store.count_chunks(document_id)
        if remaining is not None or leftover_chunks:
            logger.info(
                "document_delete_failed document_id=%s reason=sqlite_remaining",
                document_id,
            )
            raise ApiError(
                code="delete_failed",
                message="Could not remove the document record. Retry.",
                status_code=500,
            )
        logger.info(
            "document_deleted document_id=%s already_absent=false vector=%s",
            document_id,
            purge.status.value,
        )
        return DeleteResult(
            document_id=document_id,
            deleted=True,
            already_absent=False,
            vector_cleanup_status=purge.status.value,
        )

    def save_upload(self, filename: str, data: bytes) -> Path:
        if not data:
            raise IngestionError("Uploaded file is empty.", code="empty_file")
        max_bytes = self._app.settings.max_file_bytes
        if len(data) > max_bytes:
            raise IngestionError(
                f"File exceeds max size ({len(data)} > {max_bytes} bytes).",
                code="too_large",
            )
        dest = unique_destination(self._app.settings.upload_dir, filename)
        dest.write_bytes(data)
        return dest

    def _finish_prepare(self, ingested: IngestResult) -> PreparedDocument:
        if ingested.document is None or not ingested.ok:
            message = ingested.error_message or "Ingestion failed."
            code = ingested.error_type or "parse_error"
            logger.info("ingest_failed code=%s", code)
            raise error_from_domain(IngestionError(message, code=code))
        document_id = ingested.document.document_id
        chunked = self._app.chunking.chunk_document(document_id, self._chunking)
        if not chunked.ok:
            raise ApiError(
                code=chunked.error_type or "chunking_error",
                message=chunked.error_message or "Chunking failed.",
                status_code=422,
            )
        indexed = self._app.indexing.index_document(document_id, self.chunker_id)
        if not indexed.ok:
            raw = indexed.error_message or "Indexing failed."
            code = indexed.error_type or "indexing_error"
            filename = ingested.document.filename if ingested.document else None
            if looks_like_resource_exhaustion(raw) or code == RESOURCE_EXHAUSTED_CODE:
                logger.error(
                    "library_index_resource_exhausted document_id=%s filename=%s detail=%s",
                    document_id,
                    filename,
                    raw,
                )
                raise error_from_domain(
                    IngestionError(
                        public_resource_message(filename),
                        code=RESOURCE_EXHAUSTED_CODE,
                    )
                )
            logger.info("library_index_failed document_id=%s code=%s", document_id, code)
            raise error_from_domain(IngestionError(raw, code=code))
        record = self._app.store.get_by_id(document_id)
        if record is None:
            raise ApiError(
                code="not_found",
                message="Document disappeared after indexing.",
                status_code=500,
            )
        warnings = list(ingested.warnings) + list(indexed.warnings)
        parsed = ingested.parsed or _parsed_payload(record)
        warnings.extend(_document_warnings(parsed))
        logger.info(
            "library_prepare_completed document_id=%s filename=%s chunks=%s",
            document_id,
            record.filename,
            self._app.store.count_chunks(document_id, self.chunker_id),
        )
        return self._prepared_from_record(
            record,
            outcome=(
                IngestOutcome.UPDATED.value
                if ingested.outcome is IngestOutcome.UNCHANGED
                else ingested.outcome.value
            ),
            extra_warnings=tuple(dict.fromkeys(warnings)),
        )

    def _prepared_from_record(
        self,
        record: DocumentRecord,
        *,
        outcome: str,
        extra_warnings: tuple[str, ...] | list[str] = (),
    ) -> PreparedDocument:
        count = self._app.store.count_chunks(record.document_id, self.chunker_id)
        health = self._app.indexing.health.document_index_health(
            record.document_id, self.chunker_id
        )
        return PreparedDocument(
            summary=to_document_summary(
                record, chunk_count=count, indexed=health.ready, index_health=health
            ),
            outcome=outcome,
            warnings=tuple(dict.fromkeys(extra_warnings)),
        )

    def _require_record(self, document_id: str) -> DocumentRecord:
        record = self._app.store.get_by_id(document_id)
        if record is None:
            raise ApiError(
                code="not_found",
                message="Document not found.",
                status_code=404,
            )
        return record

    def _document_is_ready(self, document_id: str) -> bool:
        return self._app.indexing.health.document_index_health(document_id, self.chunker_id).ready


def _parsed_payload(record: DocumentRecord) -> ParsedDocument | None:
    try:
        return record.parsed_document()
    except (TypeError, ValueError, KeyError, AttributeError, json.JSONDecodeError):
        logger.info("parsed_payload_unreadable document_id=%s", record.document_id)
        return None


def _document_warnings(parsed: ParsedDocument | None) -> list[str]:
    if parsed is None:
        return []
    messages: list[str] = []
    for warning in parsed.warnings:
        if isinstance(warning, str):
            text = warning.strip()
        else:
            text = str(getattr(warning, "message", warning) or "").strip()
        if text:
            messages.append(text)
    return messages
