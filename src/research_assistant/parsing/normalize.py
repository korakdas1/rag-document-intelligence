"""Conservative text normalization. No hyphenation or layout heuristics."""

from __future__ import annotations

import re

_BLANK_PARAGRAPH = re.compile(r"\n\s*\n")


def normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def rstrip_lines(text: str) -> str:
    return "\n".join(line.rstrip(" \t") for line in text.split("\n"))


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines; join wrapped lines with a single space.

    Does not collapse Unicode spaces or repair hyphenated line breaks.
    """
    cleaned = rstrip_lines(normalize_line_endings(text)).strip("\n")
    if not cleaned.strip():
        return []
    paragraphs: list[str] = []
    for chunk in _BLANK_PARAGRAPH.split(cleaned):
        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        if lines:
            paragraphs.append(" ".join(lines))
    return paragraphs
