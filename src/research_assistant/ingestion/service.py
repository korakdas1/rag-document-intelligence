"""Ingestion orchestration. Call this from tests, CLI, and the HTTP API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from research_assistant.core.errors import IngestionError
from research_assistant.core.logging import get_logger
from research_assistant.core.settings import Settings, load_settings
from research_assistant.core.timing import Timer
from research_assistant.core.types import IngestOutcome, ParseStatus, VectorPurgeStatus
from research_assistant.indexing.invalidation import (
    PurgeResult,
    VectorIndexInvalidator,
    default_vector_invalidator,
)
from research_assistant.ingestion.checksum import sha256_bytes
from research_assistant.ingestion.detect import detect_content_type
from research_assistant.ingestion.identity import document_id_for_path
from research_assistant.ingestion.models import IngestResult
from research_assistant.ingestion.validate import validate_ingest_path
from research_assistant.parsing.models import ParsedDocument
from research_assistant.parsing.protocol import ParseInput
from research_assistant.parsing.registry import ParserRegistry
from research_assistant.storage.protocol import DocumentStore
from research_assistant.storage.records import DocumentRecord
from research_assistant.storage.sqlite import SqliteDocumentStore

logger = get_logger("research_assistant.ingestion")
_ERROR_MESSAGE_LIMIT = 2000


class IngestionService:
    def __init__(
        self,
        settings: Settings | None = None,
        store: DocumentStore | None = None,
        registry: ParserRegistry | None = None,
        invalidator: VectorIndexInvalidator | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._store = store or SqliteDocumentStore(self._settings.database_path)
        self._registry = registry or ParserRegistry()
        self._invalidator = invalidator or default_vector_invalidator(
            self._store,
            vector_index_path=self._settings.vector_index_path,
        )

    def get_document(self, document_id: str) -> DocumentRecord | None:
        return self._store.get_by_id(document_id)

    def ingest(self, path: str | Path, *, force: bool = False) -> IngestResult:
        source = Path(path)
        logger.info("ingestion_started path=%s force=%s", source, force)
        try:
            resolved = validate_ingest_path(
                source, max_file_bytes=self._settings.max_file_bytes
            )
            data = _read_file(resolved)
        except IngestionError as exc:
            logger.info(
                "ingestion_failed path=%s error_type=%s",
                source,
                exc.code,
            )
            return IngestResult(
                outcome=IngestOutcome.FAILED,
                source_path=str(source),
                document=None,
                error_type=exc.code,
                error_message=exc.message,
            )
        except OSError as exc:
            logger.info("ingestion_failed path=%s error_type=unreadable", source)
            return IngestResult(
                outcome=IngestOutcome.FAILED,
                source_path=str(source),
                document=None,
                error_type="unreadable",
                error_message=str(exc),
            )

        try:
            content_type = detect_content_type(resolved, data[:16])
        except IngestionError as exc:
            logger.info(
                "ingestion_failed path=%s error_type=%s",
                resolved,
                exc.code,
            )
            return IngestResult(
                outcome=IngestOutcome.FAILED,
                source_path=str(resolved),
                document=None,
                error_type=exc.code,
                error_message=exc.message,
            )

        checksum = sha256_bytes(data)
        document_id = document_id_for_path(resolved)
        existing = self._store.get_by_id(document_id)
        now = _utc_now()

        if (
            existing is not None
            and existing.checksum_sha256 == checksum
            and not force
        ):
            parsed = existing.parsed_document()
            logger.info(
                "ingestion_completed document_id=%s outcome=unchanged "
                "content_type=%s checksum=%s parser=%s warnings=%s",
                document_id,
                existing.content_type,
                checksum[:12],
                existing.parser_id,
                existing.warning_count,
            )
            return IngestResult(
                outcome=IngestOutcome.UNCHANGED,
                source_path=str(resolved),
                document=existing,
                parsed=parsed,
                error_type=existing.error_type,
                error_message=existing.error_message,
            )

        parse_input = ParseInput(
            document_id=document_id,
            path=resolved,
            data=data,
            content_type=content_type,
        )
        parser_id: str | None = None
        try:
            parser = self._registry.get(content_type)
            parser_id = parser.parser_id
            with Timer("parse") as parse_timer:
                parsed = parser.parse(parse_input)
            record = _record_from_parsed(
                document_id=document_id,
                resolved=resolved,
                content_type=content_type,
                checksum=checksum,
                byte_size=len(data),
                parsed=parsed,
                ingested_at=existing.ingested_at if existing else now,
                updated_at=now,
            )
            with Timer("persist") as persist_timer:
                self._store.upsert(record)
            purge = self._purge_stale_vectors(
                document_id, existing=existing, checksum=checksum
            )
            outcome = (
                IngestOutcome.UPDATED if existing is not None else IngestOutcome.CREATED
            )
            logger.info(
                "ingestion_completed document_id=%s outcome=%s content_type=%s "
                "parser=%s checksum=%s parse_ms=%.1f persist_ms=%.1f "
                "blocks=%s warnings=%s vector_purge=%s",
                document_id,
                outcome.value,
                content_type,
                parser_id,
                checksum[:12],
                parse_timer.seconds * 1000,
                persist_timer.seconds * 1000,
                len(parsed.blocks),
                len(parsed.warnings),
                purge.status.value if purge else VectorPurgeStatus.NOT_APPLICABLE.value,
            )
            return IngestResult(
                outcome=outcome,
                source_path=str(resolved),
                document=record,
                parsed=parsed,
                **_purge_fields(purge),
            )
        except IngestionError as exc:
            record = _failed_record(
                document_id=document_id,
                resolved=resolved,
                content_type=content_type,
                checksum=checksum,
                byte_size=len(data),
                parser_id=parser_id,
                ingested_at=existing.ingested_at if existing else now,
                updated_at=now,
                error_type=exc.code,
                error_message=exc.message,
            )
            self._store.upsert(record)
            purge = self._purge_stale_vectors(
                document_id, existing=existing, checksum=checksum
            )
            logger.info(
                "ingestion_failed document_id=%s error_type=%s parser=%s",
                document_id,
                exc.code,
                parser_id,
            )
            return IngestResult(
                outcome=IngestOutcome.FAILED,
                source_path=str(resolved),
                document=record,
                parsed=None,
                error_type=exc.code,
                error_message=exc.message,
                **_purge_fields(purge),
            )

    def _purge_stale_vectors(
        self,
        document_id: str,
        *,
        existing: DocumentRecord | None,
        checksum: str,
    ) -> PurgeResult | None:
        if existing is None or existing.checksum_sha256 == checksum:
            return None
        return self._invalidator.purge_document(document_id)


def _read_file(path: Path) -> bytes:
    with path.open("rb") as handle:
        return handle.read()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _purge_fields(purge: PurgeResult | None) -> dict[str, object]:
    if purge is None:
        return {
            "vector_purge_status": VectorPurgeStatus.NOT_APPLICABLE,
            "vector_purge_error": None,
            "warnings": (),
        }
    warnings: tuple[str, ...] = ()
    if not purge.ok:
        warnings = (f"vector_purge_failed:{purge.error_message or 'unknown'}",)
    return {
        "vector_purge_status": purge.status,
        "vector_purge_error": purge.error_message,
        "warnings": warnings,
    }


def _record_from_parsed(
    *,
    document_id: str,
    resolved: Path,
    content_type,
    checksum: str,
    byte_size: int,
    parsed: ParsedDocument,
    ingested_at: str,
    updated_at: str,
) -> DocumentRecord:
    payload = parsed.to_dict()
    return DocumentRecord(
        document_id=document_id,
        source_path=str(resolved),
        filename=resolved.name,
        content_type=content_type,
        checksum_sha256=checksum,
        byte_size=byte_size,
        ingested_at=ingested_at,
        updated_at=updated_at,
        parse_status=ParseStatus.PARSED,
        parser_id=parsed.parser_id,
        warning_count=len(parsed.warnings),
        page_count=parsed.page_count,
        parsed_json=json.dumps(payload, ensure_ascii=False),
        error_type=None,
        error_message=None,
    )


def _failed_record(
    *,
    document_id: str,
    resolved: Path,
    content_type,
    checksum: str,
    byte_size: int,
    parser_id: str | None,
    ingested_at: str,
    updated_at: str,
    error_type: str,
    error_message: str,
) -> DocumentRecord:
    message = error_message
    if len(message) > _ERROR_MESSAGE_LIMIT:
        message = message[:_ERROR_MESSAGE_LIMIT] + "…"
    return DocumentRecord(
        document_id=document_id,
        source_path=str(resolved),
        filename=resolved.name,
        content_type=content_type,
        checksum_sha256=checksum,
        byte_size=byte_size,
        ingested_at=ingested_at,
        updated_at=updated_at,
        parse_status=ParseStatus.FAILED,
        parser_id=parser_id,
        warning_count=0,
        page_count=None,
        parsed_json=None,
        error_type=error_type,
        error_message=message,
    )
