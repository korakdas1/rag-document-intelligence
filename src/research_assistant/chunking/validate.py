"""Chunk list invariants. Lossless reconstruction is not a goal (overlap duplicates text)."""

from __future__ import annotations

from collections.abc import Sequence

from research_assistant.chunking.models import Chunk
from research_assistant.core.errors import ChunkingError
from research_assistant.parsing.models import ParsedDocument


def validate_chunks(chunks: Sequence[Chunk], parsed: ParsedDocument) -> None:
    ids = [chunk.chunk_id for chunk in chunks]
    if len(ids) != len(set(ids)):
        raise ChunkingError("Duplicate chunk_id in a single run", code="duplicate_chunk_id")

    block_count = len(parsed.blocks)
    for index, chunk in enumerate(chunks):
        if chunk.document_id != parsed.document_id:
            raise ChunkingError(
                f"Chunk {chunk.chunk_id} has mismatched document_id",
                code="document_mismatch",
            )
        if chunk.position != index:
            raise ChunkingError(
                f"Chunk positions are not contiguous: expected {index}, got {chunk.position}",
                code="position_gap",
            )
        if chunk.char_count != len(chunk.text):
            raise ChunkingError(
                "char_count does not match text length",
                code="char_count_mismatch",
            )
        if not chunk.text:
            raise ChunkingError("Empty chunk text is not allowed", code="empty_chunk")
        if chunk.page_start is not None and chunk.page_end is not None:
            if chunk.page_start > chunk.page_end:
                raise ChunkingError(
                    "page_start is greater than page_end",
                    code="invalid_page_range",
                )
        if block_count:
            if not (0 <= chunk.source_block_start <= chunk.source_block_end < block_count):
                raise ChunkingError(
                    "source block span is out of range",
                    code="invalid_block_span",
                )
        if not chunk.chunker_id:
            raise ChunkingError("chunker_id is required", code="missing_chunker_id")
        if len(chunk.content_hash) != 64:
            raise ChunkingError("content_hash must be SHA-256 hex", code="bad_content_hash")
