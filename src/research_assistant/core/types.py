"""Shared enumerations for ingestion and parsing."""

from __future__ import annotations

from enum import StrEnum


class ContentType(StrEnum):
    PLAIN_TEXT = "text/plain"
    MARKDOWN = "text/markdown"
    PDF = "application/pdf"


class ParseStatus(StrEnum):
    PARSED = "parsed"
    FAILED = "failed"


class BlockKind(StrEnum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    CODE_BLOCK = "code_block"


class IngestOutcome(StrEnum):
    CREATED = "created"
    UNCHANGED = "unchanged"
    UPDATED = "updated"
    FAILED = "failed"


class ChunkingOutcome(StrEnum):
    CREATED = "created"
    REPLACED = "replaced"
    EMPTY = "empty"
    FAILED = "failed"


class IndexStatus(StrEnum):
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"


class IndexingOutcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    EMPTY = "empty"
    FAILED = "failed"


class VectorPurgeStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    PURGED = "purged"
    NOOP = "noop"
    FAILED = "failed"


class RetrievalMode(StrEnum):
    DENSE = "dense"
    LEXICAL = "lexical"
    HYBRID = "hybrid"
