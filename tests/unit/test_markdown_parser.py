from pathlib import Path

from research_assistant.core.types import BlockKind, ContentType
from research_assistant.parsing.markdown import MarkdownParser
from research_assistant.parsing.protocol import ParseInput
from tests.conftest import FIXTURES


def test_markdown_structure_and_code_block() -> None:
    path = FIXTURES / "markdown" / "structure.md"
    parsed = MarkdownParser().parse(
        ParseInput(
            document_id="md-test",
            path=path,
            data=path.read_bytes(),
            content_type=ContentType.MARKDOWN,
        )
    )
    kinds = [block.kind for block in parsed.blocks]
    assert BlockKind.HEADING in kinds
    assert BlockKind.PARAGRAPH in kinds
    assert BlockKind.LIST_ITEM in kinds
    assert BlockKind.CODE_BLOCK in kinds

    headings = [block for block in parsed.blocks if block.kind is BlockKind.HEADING]
    assert headings[0].text == "Introduction"
    assert headings[0].heading_level == 1
    assert headings[1].text == "Methods"
    assert headings[1].heading_level == 2

    methods_para_or_list = [
        block
        for block in parsed.blocks
        if block.section_path[:1] == ("Introduction",) or "Methods" in block.section_path
    ]
    assert methods_para_or_list

    code = next(block for block in parsed.blocks if block.kind is BlockKind.CODE_BLOCK)
    assert 'print("hello")' in code.text
    assert "x = 1" in code.text

    conclusion = next(block for block in parsed.blocks if block.text == "Conclusion")
    assert conclusion.section_path == ("Conclusion",)
