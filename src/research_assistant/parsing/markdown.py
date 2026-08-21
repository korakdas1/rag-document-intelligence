"""Structure-preserving Markdown extractor.

Not a CommonMark renderer. ATX headings, fenced code, and simple lists
are recognized so the chunker can split by section. Emphasis markers are left intact.
"""

from __future__ import annotations

import re

from research_assistant.core.errors import DecodeError
from research_assistant.core.types import BlockKind, ContentType
from research_assistant.parsing.models import ParsedDocument, TextBlock
from research_assistant.parsing.normalize import normalize_line_endings, rstrip_lines
from research_assistant.parsing.protocol import ParseInput

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_UL_ITEM = re.compile(r"^(\s*)[-*+]\s+(.+)$")
_OL_ITEM = re.compile(r"^(\s*)\d+\.\s+(.+)$")
_FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")


class MarkdownParser:
    parser_id = "markdown.v1"

    def supports(self, content_type: ContentType) -> bool:
        return content_type is ContentType.MARKDOWN

    def parse(self, source: ParseInput) -> ParsedDocument:
        try:
            raw = source.data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DecodeError(
                f"File is not valid UTF-8: {source.path} ({exc.reason})"
            ) from exc

        lines = rstrip_lines(normalize_line_endings(raw)).split("\n")
        blocks: list[TextBlock] = []
        warnings: list[str] = []
        heading_stack: list[tuple[int, str]] = []
        paragraph_lines: list[str] = []
        fence_marker: str | None = None
        fence_lines: list[str] = []

        def section_path() -> tuple[str, ...]:
            return tuple(title for _, title in heading_stack)

        def flush_paragraph() -> None:
            nonlocal paragraph_lines
            text = " ".join(line.strip() for line in paragraph_lines if line.strip())
            paragraph_lines = []
            if not text:
                return
            blocks.append(
                TextBlock(
                    position=len(blocks),
                    kind=BlockKind.PARAGRAPH,
                    text=text,
                    section_path=section_path(),
                )
            )

        def update_headings(level: int, title: str) -> None:
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))

        for line in lines:
            if fence_marker is not None:
                if line.startswith(fence_marker) and _FENCE.match(line):
                    code = "\n".join(fence_lines)
                    blocks.append(
                        TextBlock(
                            position=len(blocks),
                            kind=BlockKind.CODE_BLOCK,
                            text=code,
                            section_path=section_path(),
                        )
                    )
                    fence_marker = None
                    fence_lines = []
                else:
                    fence_lines.append(line)
                continue

            fence_match = _FENCE.match(line)
            if fence_match:
                flush_paragraph()
                fence_marker = fence_match.group(1)
                fence_lines = []
                continue

            if not line.strip():
                flush_paragraph()
                continue

            heading_match = _HEADING.match(line)
            if heading_match:
                flush_paragraph()
                level = len(heading_match.group(1))
                title = heading_match.group(2).rstrip("#").strip()
                update_headings(level, title)
                blocks.append(
                    TextBlock(
                        position=len(blocks),
                        kind=BlockKind.HEADING,
                        text=title,
                        heading_level=level,
                        section_path=section_path(),
                    )
                )
                continue

            list_match = _UL_ITEM.match(line) or _OL_ITEM.match(line)
            if list_match:
                flush_paragraph()
                item_text = list_match.group(2).strip()
                blocks.append(
                    TextBlock(
                        position=len(blocks),
                        kind=BlockKind.LIST_ITEM,
                        text=item_text,
                        section_path=section_path(),
                    )
                )
                continue

            paragraph_lines.append(line)

        if fence_marker is not None:
            warnings.append("unclosed_code_fence")
            code = "\n".join(fence_lines)
            blocks.append(
                TextBlock(
                    position=len(blocks),
                    kind=BlockKind.CODE_BLOCK,
                    text=code,
                    section_path=section_path(),
                )
            )
        else:
            flush_paragraph()

        if not blocks:
            warnings.append("empty_document")

        return ParsedDocument(
            document_id=source.document_id,
            blocks=tuple(blocks),
            parser_id=self.parser_id,
            warnings=tuple(warnings),
        )
