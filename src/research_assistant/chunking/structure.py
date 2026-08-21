"""Structure-aware chunker. Uses headings, pages, and block kinds from parsing."""

from __future__ import annotations

from collections.abc import Sequence

from research_assistant.chunking.assemble import (
    common_section_path,
    join_block_texts,
    locator_warnings,
    overlap_suffix_blocks,
    page_range,
)
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.chunking.models import Chunk, build_chunk
from research_assistant.chunking.split import split_oversized_block
from research_assistant.core.types import BlockKind
from research_assistant.parsing.models import ParsedDocument, TextBlock


class StructureAwareChunker:
    strategy_name = "structure"

    def chunk(
        self, parsed: ParsedDocument, config: ChunkingConfig
    ) -> tuple[Chunk, ...]:
        if not parsed.blocks:
            return ()

        expanded = [
            block
            for block in _expand_oversized(parsed.blocks, config.max_chars)
            if block.text
        ]
        if not expanded:
            return ()
        chunks: list[Chunk] = []
        current: list[TextBlock] = []
        pending_overlap: tuple[TextBlock, ...] = ()
        overlap_only = False

        def flush(*, section_break: bool) -> None:
            nonlocal current, pending_overlap, overlap_only
            if not current or not join_block_texts(current):
                current = []
                overlap_only = False
                return
            chunk = _chunk_from_blocks(
                parsed.document_id,
                config.chunker_id,
                len(chunks),
                current,
            )
            chunks.append(chunk)
            if section_break:
                pending_overlap = ()
            else:
                pending_overlap = overlap_suffix_blocks(current, config.overlap_chars)
            current = []
            overlap_only = False

        for block in expanded:
            if not current and pending_overlap:
                if _same_section(pending_overlap, block):
                    projected = len(join_block_texts([*pending_overlap, block]))
                    if projected <= config.max_chars:
                        current.extend(pending_overlap)
                        overlap_only = True
                pending_overlap = ()

            if current and _should_break(current, block, config):
                # Drop only an overlap prefix that cannot fit with the next
                # block. Never drop leftover source text.
                if overlap_only and len(join_block_texts(current)) < config.min_chars:
                    current = []
                    pending_overlap = ()
                    overlap_only = False
                else:
                    flush(section_break=_is_heading_boundary(block))
                    if pending_overlap and _same_section(pending_overlap, block):
                        projected = len(join_block_texts([*pending_overlap, block]))
                        if projected <= config.max_chars:
                            current.extend(pending_overlap)
                            overlap_only = True
                        pending_overlap = ()

            current.append(block)
            overlap_only = False
            if len(join_block_texts(current)) >= config.max_chars:
                flush(section_break=False)

        flush(section_break=False)
        return tuple(chunks)


def _expand_oversized(
    blocks: Sequence[TextBlock], max_chars: int
) -> list[TextBlock]:
    expanded: list[TextBlock] = []
    for block in blocks:
        expanded.extend(split_oversized_block(block, max_chars))
    return expanded


def _should_break(
    current: list[TextBlock], incoming: TextBlock, config: ChunkingConfig
) -> bool:
    size = len(join_block_texts(current))
    projected = len(join_block_texts([*current, incoming]))
    if current and projected > config.max_chars:
        return True
    if size < config.min_chars:
        return False
    if config.prefer_section_boundaries and _is_heading_boundary(incoming):
        return True
    if (
        incoming.page is not None
        and current[-1].page is not None
        and incoming.page != current[-1].page
        and size >= config.target_chars
    ):
        return True
    return projected > config.target_chars


def _is_heading_boundary(block: TextBlock) -> bool:
    return block.kind is BlockKind.HEADING


def _same_section(blocks: Sequence[TextBlock], incoming: TextBlock) -> bool:
    if not blocks:
        return True
    return common_section_path(blocks) == common_section_path([blocks[-1], incoming]) or (
        blocks[-1].section_path == incoming.section_path
    )


def _chunk_from_blocks(
    document_id: str,
    chunker_id: str,
    position: int,
    blocks: Sequence[TextBlock],
) -> Chunk:
    text = join_block_texts(blocks)
    warnings = locator_warnings(blocks)
    if any(len(block.text) for block in blocks) and not text:
        warnings.append("empty_after_join")
    page_start, page_end = page_range(blocks)
    starts = [block.position for block in blocks]
    extra: list[str] = []
    if len(starts) != len(set(starts)):
        extra.append("contains_split_block")
    return build_chunk(
        document_id=document_id,
        chunker_id=chunker_id,
        position=position,
        text=text,
        source_block_start=min(starts),
        source_block_end=max(starts),
        page_start=page_start,
        page_end=page_end,
        section_path=common_section_path(blocks),
        warnings=tuple(warnings + extra),
    )
