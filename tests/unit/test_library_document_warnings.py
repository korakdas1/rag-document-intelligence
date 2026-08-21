"""Document warning extraction must accept parser string warnings."""

from __future__ import annotations

from research_assistant.api.library import _document_warnings
from research_assistant.parsing.models import ParsedDocument


def test_document_warnings_accepts_plain_strings() -> None:
    parsed = ParsedDocument(
        document_id="doc-1",
        blocks=(),
        parser_id="markdown.v1",
        warnings=("unclosed_code_fence", "empty_document"),
    )
    assert _document_warnings(parsed) == ["unclosed_code_fence", "empty_document"]


def test_document_warnings_accepts_message_objects() -> None:
    class WarningObject:
        message = "page_1_empty"

    parsed = ParsedDocument(
        document_id="doc-1",
        blocks=(),
        parser_id="pdf.v1",
        warnings=(WarningObject(),),  # type: ignore[arg-type]
    )
    assert _document_warnings(parsed) == ["page_1_empty"]


def test_document_warnings_empty_when_missing() -> None:
    assert _document_warnings(None) == []
