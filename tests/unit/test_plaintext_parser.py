from pathlib import Path

import pytest

from research_assistant.core.errors import DecodeError
from research_assistant.core.types import BlockKind, ContentType
from research_assistant.parsing.plaintext import PlainTextParser
from research_assistant.parsing.protocol import ParseInput
from tests.conftest import FIXTURES


def _parse(path: Path, data: bytes | None = None):
    payload = path.read_bytes() if data is None else data
    return PlainTextParser().parse(
        ParseInput(
            document_id="doc-test",
            path=path,
            data=payload,
            content_type=ContentType.PLAIN_TEXT,
        )
    )


def test_paragraphs_and_unicode() -> None:
    parsed = _parse(FIXTURES / "txt" / "paragraphs_unicode.txt")
    texts = [block.text for block in parsed.blocks]
    assert len(texts) == 3
    assert "café" in texts[0]
    assert "naïve" in texts[0]
    assert "wrapped across two lines" in texts[1]
    assert "第三段落" in texts[2]
    assert all(block.kind is BlockKind.PARAGRAPH for block in parsed.blocks)


def test_empty_document_warns() -> None:
    parsed = _parse(FIXTURES / "txt" / "empty.txt")
    assert parsed.blocks == ()
    assert "empty_document" in parsed.warnings


def test_crlf_line_endings(tmp_path: Path) -> None:
    path = tmp_path / "win.txt"
    path.write_bytes(b"one\r\n\r\ntwo\r\n")
    parsed = _parse(path)
    assert [block.text for block in parsed.blocks] == ["one", "two"]


def test_invalid_utf8_fails_clearly() -> None:
    path = FIXTURES / "txt" / "invalid_utf8.txt"
    with pytest.raises(DecodeError) as exc:
        _parse(path)
    assert "UTF-8" in str(exc.value)
