from research_assistant.chunking.config import ChunkingConfig
from research_assistant.chunking.structure import StructureAwareChunker
from research_assistant.chunking.window import WindowChunker
from research_assistant.core.types import BlockKind
from tests.unit.chunking_fixtures import block, parsed


def _cfg(**overrides: object) -> ChunkingConfig:
    values = dict(
        strategy="structure",
        target_chars=80,
        max_chars=120,
        min_chars=20,
        overlap_chars=15,
        prefer_section_boundaries=True,
    )
    values.update(overrides)
    return ChunkingConfig(**values)  # type: ignore[arg-type]


def test_empty_document_returns_no_chunks() -> None:
    chunks = StructureAwareChunker().chunk(parsed(), _cfg())
    assert chunks == ()


def test_tiny_document_is_one_chunk() -> None:
    doc = parsed(block(0, "Short."))
    chunks = StructureAwareChunker().chunk(doc, _cfg())
    assert len(chunks) == 1
    assert chunks[0].text == "Short."
    assert chunks[0].source_block_start == 0
    assert chunks[0].source_block_end == 0


def test_determinism_same_input_same_ids() -> None:
    doc = parsed(
        block(0, "Introduction", kind=BlockKind.HEADING, heading_level=1, section_path=("Introduction",)),
        block(1, "A" * 50, section_path=("Introduction",)),
        block(2, "Methods", kind=BlockKind.HEADING, heading_level=1, section_path=("Methods",)),
        block(3, "B" * 50, section_path=("Methods",)),
    )
    cfg = _cfg()
    first = StructureAwareChunker().chunk(doc, cfg)
    second = StructureAwareChunker().chunk(doc, cfg)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.text for c in first] == [c.text for c in second]
    assert [c.position for c in first] == list(range(len(first)))


def test_headings_influence_boundaries_and_section_path() -> None:
    doc = parsed(
        block(0, "Introduction", kind=BlockKind.HEADING, heading_level=1, section_path=("Introduction",)),
        block(1, "Alpha paragraph about retrieval quality.", section_path=("Introduction",)),
        block(2, "Methods", kind=BlockKind.HEADING, heading_level=1, section_path=("Methods",)),
        block(3, "Beta paragraph about chunking strategy.", section_path=("Methods",)),
    )
    chunks = StructureAwareChunker().chunk(doc, _cfg(min_chars=10, target_chars=60, max_chars=90))
    assert len(chunks) >= 2
    intro = [c for c in chunks if c.section_path[:1] == ("Introduction",)]
    methods = [c for c in chunks if c.section_path[:1] == ("Methods",)]
    assert intro
    assert methods
    assert all("crosses_sections" not in c.warnings for c in intro)
    assert all("crosses_sections" not in c.warnings for c in methods)


def test_code_block_not_truncated() -> None:
    code = "line\n" * 40 + "END"
    doc = parsed(
        block(0, "Intro", kind=BlockKind.HEADING, heading_level=1, section_path=("Intro",)),
        block(1, code, kind=BlockKind.CODE_BLOCK, section_path=("Intro",)),
    )
    chunks = StructureAwareChunker().chunk(doc, _cfg(max_chars=80, target_chars=60, min_chars=10))
    joined = "\n".join(c.text for c in chunks)
    assert "END" in joined
    assert any("END" in c.text for c in chunks)


def test_pdf_page_range_spans_pages() -> None:
    doc = parsed(
        block(0, "Page one text that is moderately long for a chunk.", page=1),
        block(1, "Page two text that continues the same argument.", page=2),
    )
    chunks = StructureAwareChunker().chunk(
        doc, _cfg(target_chars=500, max_chars=600, min_chars=10, overlap_chars=0)
    )
    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 2
    assert "crosses_pages" in chunks[0].warnings


def test_page_boundary_can_split_when_target_reached() -> None:
    doc = parsed(
        block(0, "P" * 50, page=1),
        block(1, "Q" * 50, page=2),
    )
    chunks = StructureAwareChunker().chunk(
        doc, _cfg(target_chars=50, max_chars=100, min_chars=20, overlap_chars=0)
    )
    assert len(chunks) == 2
    assert chunks[0].page_start == chunks[0].page_end == 1
    assert chunks[1].page_start == chunks[1].page_end == 2


def test_overlap_is_deterministic_and_skips_section_breaks() -> None:
    doc = parsed(
        block(0, "AAAA " * 10, section_path=("A",)),
        block(1, "BBBB " * 10, section_path=("A",)),
        block(2, "Next", kind=BlockKind.HEADING, heading_level=1, section_path=("Next",)),
        block(3, "CCCC " * 10, section_path=("Next",)),
    )
    cfg = _cfg(target_chars=50, max_chars=80, min_chars=20, overlap_chars=20)
    first = StructureAwareChunker().chunk(doc, cfg)
    second = StructureAwareChunker().chunk(doc, cfg)
    assert [c.text for c in first] == [c.text for c in second]
    heading_chunks = [c for c in first if "Next" in c.text and c.section_path[:1] == ("Next",)]
    assert heading_chunks
    assert not heading_chunks[0].text.startswith("BBBB")


def test_changed_config_changes_chunker_id() -> None:
    a = _cfg(target_chars=80)
    b = _cfg(target_chars=40, max_chars=80, min_chars=10)
    assert a.chunker_id != b.chunker_id
    doc = parsed(block(0, "X" * 90))
    left = StructureAwareChunker().chunk(doc, a)
    right = StructureAwareChunker().chunk(doc, b)
    assert {c.chunker_id for c in left} != {c.chunker_id for c in right}


def test_window_chunker_overlap_and_partial_blocks() -> None:
    text = "abcdefghij" * 12
    doc = parsed(block(0, text))
    cfg = ChunkingConfig(
        strategy="window",
        target_chars=40,
        max_chars=60,
        min_chars=10,
        overlap_chars=10,
    )
    chunks = WindowChunker().chunk(doc, cfg)
    assert len(chunks) >= 3
    assert chunks[0].text == text[:40]
    assert chunks[1].text.startswith(text[30:40])
    assert chunks[0].text[-10:] == chunks[1].text[:10]
    assert all(c.source_block_start == 0 and c.source_block_end == 0 for c in chunks)


def test_tiny_leftover_before_huge_block_is_not_dropped() -> None:
    leftover = "KeepMe"
    huge = "Z" * 120
    doc = parsed(block(0, leftover), block(1, huge))
    chunks = StructureAwareChunker().chunk(
        doc, _cfg(target_chars=80, max_chars=120, min_chars=20, overlap_chars=0)
    )
    blob = "\n".join(chunk.text for chunk in chunks)
    assert leftover in blob
    assert huge in blob


def test_window_does_not_drop_tail() -> None:
    doc = parsed(block(0, "abcdefghijklmnopqrstuvwxyz"))
    cfg = ChunkingConfig(
        strategy="window",
        target_chars=10,
        max_chars=12,
        min_chars=4,
        overlap_chars=2,
    )
    chunks = WindowChunker().chunk(doc, cfg)
    assert chunks[-1].text.endswith("z")
    assert "z" in "".join(c.text for c in chunks)
