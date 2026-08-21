from pathlib import Path

from research_assistant.core.errors import ParseError
from research_assistant.core.types import ContentType
from research_assistant.parsing.pdf import PdfParser
from research_assistant.parsing.protocol import ParseInput
from tests.conftest import FIXTURES

PARSER = PdfParser()


def _parse(name: str):
    path = FIXTURES / "pdf" / name
    return PARSER.parse(
        ParseInput(
            document_id="pdf-test",
            path=path,
            data=path.read_bytes(),
            content_type=ContentType.PDF,
        )
    )


def test_multi_page_preserves_order_and_page_numbers() -> None:
    parsed = _parse("multi_page.pdf")
    assert parsed.page_count == 3
    pages = [block.page for block in parsed.blocks]
    assert pages == sorted(pages)
    assert 1 in pages and 2 in pages and 3 in pages
    joined = parsed.full_text()
    assert "Page one title" in joined
    assert "Beta paragraph lives on page two." in joined
    assert "Gamma concludes the fixture." in joined
    assert parsed.blocks[0].page == 1
    assert any(block.page == 3 for block in parsed.blocks)


def test_empty_page_is_distinguished() -> None:
    parsed = _parse("empty_middle.pdf")
    assert parsed.page_count == 3
    assert "page_2_empty" in parsed.warnings
    pages_with_text = {block.page for block in parsed.blocks}
    assert pages_with_text == {1, 3}


def test_unicode_latin1() -> None:
    parsed = _parse("unicode.pdf")
    text = parsed.full_text()
    assert "café" in text
    assert "naïve" in text
    assert "résumé" in text


def test_image_only_warns_and_does_not_ocr() -> None:
    parsed = _parse("image_only.pdf")
    assert parsed.blocks == ()
    assert "no_extractable_text" in parsed.warnings
    assert "ocr_not_attempted" in parsed.warnings
    assert any("xobjects" in warning for warning in parsed.warnings)


def test_corrupt_pdf_raises_parse_error() -> None:
    path = FIXTURES / "pdf" / "corrupt.pdf"
    try:
        PARSER.parse(
            ParseInput(
                document_id="bad",
                path=path,
                data=path.read_bytes(),
                content_type=ContentType.PDF,
            )
        )
    except ParseError:
        return
    raise AssertionError("expected ParseError for corrupt PDF")
