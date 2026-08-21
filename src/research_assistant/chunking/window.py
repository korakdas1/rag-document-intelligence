"""Fixed-window baseline chunker. Character windows with deterministic overlap."""

from __future__ import annotations

from research_assistant.chunking.assemble import (
    BLOCK_SEPARATOR,
    common_section_path,
    locator_warnings,
    page_range,
)
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.chunking.models import Chunk, build_chunk
from research_assistant.parsing.models import ParsedDocument, TextBlock


class WindowChunker:
    strategy_name = "window"

    def chunk(
        self, parsed: ParsedDocument, config: ChunkingConfig
    ) -> tuple[Chunk, ...]:
        blocks = [block for block in parsed.blocks if block.text]
        if not blocks:
            return ()

        full, spans = _concat_with_spans(blocks)
        if not full:
            return ()

        chunks: list[Chunk] = []
        start = 0
        length = len(full)
        while start < length:
            end = min(start + config.target_chars, length)
            if end < length and (end - start) < config.min_chars:
                end = min(start + config.max_chars, length)
            text = full[start:end]
            covered = [
                block
                for block in blocks
                if _overlaps(spans[block.position], start, end)
            ]
            warnings = locator_warnings(covered)
            first_span = spans[covered[0].position]
            last_span = spans[covered[-1].position]
            if first_span[0] < start or last_span[1] > end:
                warnings.append("partial_block")
            page_start, page_end = page_range(covered)
            chunks.append(
                build_chunk(
                    document_id=parsed.document_id,
                    chunker_id=config.chunker_id,
                    position=len(chunks),
                    text=text,
                    source_block_start=covered[0].position,
                    source_block_end=covered[-1].position,
                    page_start=page_start,
                    page_end=page_end,
                    section_path=common_section_path(covered),
                    warnings=tuple(warnings),
                )
            )
            if end >= length:
                break
            next_start = end - config.overlap_chars
            if next_start <= start:
                next_start = start + 1
            start = next_start
        return tuple(chunks)


def _concat_with_spans(
    blocks: list[TextBlock],
) -> tuple[str, dict[int, tuple[int, int]]]:
    parts: list[str] = []
    spans: dict[int, tuple[int, int]] = {}
    offset = 0
    for index, block in enumerate(blocks):
        if index:
            offset += len(BLOCK_SEPARATOR)
            parts.append(BLOCK_SEPARATOR)
        start = offset
        parts.append(block.text)
        offset = start + len(block.text)
        spans[block.position] = (start, offset)
    return "".join(parts), spans


def _overlaps(span: tuple[int, int], start: int, end: int) -> bool:
    block_start, block_end = span
    return block_start < end and block_end > start
