"""UTF-8 plain-text parser."""

from __future__ import annotations

from research_assistant.core.errors import DecodeError
from research_assistant.core.types import BlockKind, ContentType
from research_assistant.parsing.models import ParsedDocument, TextBlock
from research_assistant.parsing.normalize import split_paragraphs
from research_assistant.parsing.protocol import ParseInput


class PlainTextParser:
    parser_id = "plaintext.v1"

    def supports(self, content_type: ContentType) -> bool:
        return content_type is ContentType.PLAIN_TEXT

    def parse(self, source: ParseInput) -> ParsedDocument:
        try:
            text = source.data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DecodeError(
                f"File is not valid UTF-8: {source.path} ({exc.reason})"
            ) from exc

        paragraphs = split_paragraphs(text)
        warnings: list[str] = []
        if not paragraphs:
            warnings.append("empty_document")

        blocks = tuple(
            TextBlock(position=index, kind=BlockKind.PARAGRAPH, text=paragraph)
            for index, paragraph in enumerate(paragraphs)
        )
        return ParsedDocument(
            document_id=source.document_id,
            blocks=blocks,
            parser_id=self.parser_id,
            warnings=tuple(warnings),
        )
