"""Persisted document metadata. Parsed payload is JSON text, not a SQL AST."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from research_assistant.core.types import ContentType, IndexStatus, ParseStatus
from research_assistant.parsing.models import ParsedDocument


DEFAULT_SESSION_TITLE = "New research"
MAX_SESSION_TITLE_LENGTH = 80


@dataclass(frozen=True)
class DocumentRecord:
    document_id: str
    source_path: str
    filename: str
    content_type: ContentType
    checksum_sha256: str
    byte_size: int
    ingested_at: str
    updated_at: str
    parse_status: ParseStatus
    parser_id: str | None
    warning_count: int
    page_count: int | None
    parsed_json: str | None
    error_type: str | None = None
    error_message: str | None = None

    def parsed_document(self) -> ParsedDocument | None:
        if not self.parsed_json:
            return None
        payload: dict[str, Any] = json.loads(self.parsed_json)
        return ParsedDocument.from_dict(payload)


@dataclass(frozen=True)
class IndexMetadata:
    index_id: str
    collection_name: str
    embedding_model_id: str
    chunker_id: str
    dimension: int
    metric: str
    normalized: bool
    schema_version: int
    backend: str
    status: IndexStatus
    chunk_count: int
    created_at: str
    updated_at: str
    error_message: str | None = None


@dataclass(frozen=True)
class SessionRecord:
    session_id: str
    title: str
    created_at: str
    updated_at: str
    all_documents: bool
    selected_document_ids: tuple[str, ...]
    turn_count: int = 0


@dataclass(frozen=True)
class SessionTurnRecord:
    turn_id: str
    session_id: str
    sequence: int
    question: str
    original_question: str | None
    retrieval_query: str | None
    generation_question: str | None
    answer: str
    grounding_status: str
    validation_status: str | None
    insufficient_evidence: bool
    error_message: str | None
    sources_json: str
    citations_json: str
    diagnostics_json: str | None
    created_at: str
