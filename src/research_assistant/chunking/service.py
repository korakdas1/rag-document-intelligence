"""Chunking orchestration. Call this from tests and CLI, not from parser code."""

from __future__ import annotations

from dataclasses import dataclass

from research_assistant.chunking.config import ChunkingConfig, default_config
from research_assistant.chunking.models import Chunk
from research_assistant.chunking.registry import ChunkerRegistry
from research_assistant.chunking.validate import validate_chunks
from research_assistant.core.errors import ChunkingError
from research_assistant.core.logging import get_logger
from research_assistant.core.settings import Settings, load_settings
from research_assistant.core.timing import Timer
from research_assistant.core.types import ChunkingOutcome, ParseStatus
from research_assistant.parsing.models import ParsedDocument
from research_assistant.storage.sqlite import SqliteDocumentStore

logger = get_logger("research_assistant.chunking")


@dataclass(frozen=True)
class ChunkingResult:
    outcome: ChunkingOutcome
    document_id: str
    chunker_id: str
    chunks: tuple[Chunk, ...]
    error_type: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.outcome is not ChunkingOutcome.FAILED


class ChunkingService:
    def __init__(
        self,
        settings: Settings | None = None,
        store: SqliteDocumentStore | None = None,
        registry: ChunkerRegistry | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._store = store or SqliteDocumentStore(self._settings.database_path)
        self._registry = registry or ChunkerRegistry()

    def chunk_parsed(
        self, parsed: ParsedDocument, config: ChunkingConfig | None = None
    ) -> tuple[Chunk, ...]:
        cfg = config or default_config()
        chunker = self._registry.get(cfg)
        chunks = chunker.chunk(parsed, cfg)
        validate_chunks(chunks, parsed)
        return chunks

    def chunk_document(
        self, document_id: str, config: ChunkingConfig | None = None
    ) -> ChunkingResult:
        cfg = config or default_config()
        logger.info(
            "chunking_started document_id=%s chunker_id=%s",
            document_id,
            cfg.chunker_id,
        )
        record = self._store.get_by_id(document_id)
        if record is None:
            return ChunkingResult(
                outcome=ChunkingOutcome.FAILED,
                document_id=document_id,
                chunker_id=cfg.chunker_id,
                chunks=(),
                error_type="not_found",
                error_message=f"No document with id {document_id}",
            )
        if record.parse_status is not ParseStatus.PARSED:
            return ChunkingResult(
                outcome=ChunkingOutcome.FAILED,
                document_id=document_id,
                chunker_id=cfg.chunker_id,
                chunks=(),
                error_type="not_parsed",
                error_message="Document is not in parsed state",
            )
        parsed = record.parsed_document()
        if parsed is None:
            return ChunkingResult(
                outcome=ChunkingOutcome.FAILED,
                document_id=document_id,
                chunker_id=cfg.chunker_id,
                chunks=(),
                error_type="missing_parsed_payload",
                error_message="Document has no parsed_json",
            )

        existing = self._store.list_chunks(document_id, cfg.chunker_id)
        try:
            with Timer("chunk") as timer:
                chunks = self.chunk_parsed(parsed, cfg)
        except ChunkingError as exc:
            logger.info(
                "chunking_failed document_id=%s error_type=%s",
                document_id,
                exc.code,
            )
            return ChunkingResult(
                outcome=ChunkingOutcome.FAILED,
                document_id=document_id,
                chunker_id=cfg.chunker_id,
                chunks=(),
                error_type=exc.code,
                error_message=exc.message,
            )

        if not chunks:
            self._store.replace_chunks(document_id, cfg.chunker_id, ())
            logger.info(
                "chunking_completed document_id=%s outcome=empty chunker_id=%s",
                document_id,
                cfg.chunker_id,
            )
            return ChunkingResult(
                outcome=ChunkingOutcome.EMPTY,
                document_id=document_id,
                chunker_id=cfg.chunker_id,
                chunks=(),
            )

        self._store.replace_chunks(document_id, cfg.chunker_id, chunks)
        outcome = (
            ChunkingOutcome.REPLACED if existing else ChunkingOutcome.CREATED
        )
        logger.info(
            "chunking_completed document_id=%s outcome=%s chunker_id=%s "
            "chunks=%s chunk_ms=%.1f",
            document_id,
            outcome.value,
            cfg.chunker_id,
            len(chunks),
            timer.seconds * 1000,
        )
        return ChunkingResult(
            outcome=outcome,
            document_id=document_id,
            chunker_id=cfg.chunker_id,
            chunks=chunks,
        )

    def list_chunks(
        self, document_id: str, chunker_id: str | None = None
    ) -> tuple[Chunk, ...]:
        return tuple(self._store.list_chunks(document_id, chunker_id))
