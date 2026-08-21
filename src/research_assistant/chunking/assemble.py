"""Shared text joining and locator derivation. Chunkers must not re-parse files."""

from __future__ import annotations

from collections.abc import Sequence

from research_assistant.parsing.models import TextBlock

BLOCK_SEPARATOR = "\n\n"


def join_block_texts(blocks: Sequence[TextBlock]) -> str:
    return BLOCK_SEPARATOR.join(block.text for block in blocks if block.text)


def common_section_path(blocks: Sequence[TextBlock]) -> tuple[str, ...]:
    paths = [block.section_path for block in blocks]
    if not paths:
        return ()
    prefix = list(paths[0])
    for path in paths[1:]:
        limit = 0
        while limit < len(prefix) and limit < len(path) and prefix[limit] == path[limit]:
            limit += 1
        prefix = prefix[:limit]
    return tuple(prefix)


def page_range(blocks: Sequence[TextBlock]) -> tuple[int | None, int | None]:
    pages = [block.page for block in blocks if block.page is not None]
    if not pages:
        return None, None
    return min(pages), max(pages)


def locator_warnings(blocks: Sequence[TextBlock]) -> list[str]:
    warnings: list[str] = []
    if not blocks:
        return warnings
    paths = [block.section_path for block in blocks]
    if any(path != paths[0] for path in paths):
        warnings.append("crosses_sections")
    pages = [block.page for block in blocks if block.page is not None]
    if pages and min(pages) != max(pages):
        warnings.append("crosses_pages")
    return warnings


def overlap_suffix_blocks(
    blocks: Sequence[TextBlock], overlap_chars: int
) -> tuple[TextBlock, ...]:
    """Trailing whole blocks whose joined size is <= overlap_chars."""
    if overlap_chars <= 0 or not blocks:
        return ()
    selected: list[TextBlock] = []
    for block in reversed(blocks):
        candidate = [block, *selected]
        size = len(join_block_texts(candidate))
        if size > overlap_chars:
            break
        selected = candidate
        if size >= overlap_chars:
            break
    return tuple(selected)
