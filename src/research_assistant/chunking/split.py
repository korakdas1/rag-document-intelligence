"""Split oversized blocks without dropping text."""

from __future__ import annotations

from research_assistant.core.types import BlockKind
from research_assistant.parsing.models import TextBlock


def split_oversized_block(block: TextBlock, max_chars: int) -> tuple[TextBlock, ...]:
    """Yield same-locator slices. Never truncates. Does not invent new block positions."""
    if len(block.text) <= max_chars:
        return (block,)
    pieces = (
        _split_code_lines(block.text, max_chars)
        if block.kind is BlockKind.CODE_BLOCK
        else _split_text(block.text, max_chars)
    )
    return tuple(
        TextBlock(
            position=block.position,
            kind=block.kind,
            text=piece,
            page=block.page,
            heading_level=block.heading_level,
            section_path=block.section_path,
        )
        for piece in pieces
        if piece
    )


def _split_code_lines(text: str, max_chars: int) -> list[str]:
    lines = text.split("\n")
    parts: list[str] = []
    current: list[str] = []
    for line in lines:
        if len(line) > max_chars:
            if current:
                parts.append("\n".join(current))
                current = []
            parts.extend(_split_text(line, max_chars))
            continue
        candidate = "\n".join([*current, line]) if current else line
        if current and len(candidate) > max_chars:
            parts.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        parts.append("\n".join(current))
    return parts


def _split_text(text: str, max_chars: int) -> list[str]:
    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            parts.append(remaining)
            break
        window = remaining[:max_chars]
        cut = window.rfind("\n")
        if cut < max_chars // 4:
            cut = window.rfind(" ")
        if cut < max_chars // 4:
            cut = max_chars
        parts.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
        if remaining.startswith(" "):
            remaining = remaining[1:]
    return [part for part in parts if part]
