import pytest

from research_assistant.chunking.models import build_chunk
from research_assistant.core.errors import RetrievalError
from research_assistant.retrieval.filters import RetrievalFilter, chunk_matches_filter


def _chunk(**kwargs):
    defaults = dict(
        document_id="doc-a",
        chunker_id="structure.v1:test",
        position=0,
        text="hello",
        source_block_start=0,
        source_block_end=0,
        page_start=None,
        page_end=None,
        section_path=(),
    )
    defaults.update(kwargs)
    return build_chunk(**defaults)


def test_document_filter() -> None:
    chunk = _chunk(document_id="doc-a")
    assert chunk_matches_filter(chunk, RetrievalFilter(document_ids=("doc-a",)))
    assert not chunk_matches_filter(chunk, RetrievalFilter(document_ids=("doc-b",)))


def test_page_overlap() -> None:
    chunk = _chunk(page_start=4, page_end=6)
    assert chunk_matches_filter(chunk, RetrievalFilter(page=5))
    assert not chunk_matches_filter(chunk, RetrievalFilter(page=7))
    assert not chunk_matches_filter(_chunk(), RetrievalFilter(page=5))


def test_section_prefix() -> None:
    chunk = _chunk(section_path=("Methods", "Training"))
    assert chunk_matches_filter(chunk, RetrievalFilter(section_prefix=("Methods",)))
    assert chunk_matches_filter(
        chunk, RetrievalFilter(section_prefix=("Methods", "Training"))
    )
    assert not chunk_matches_filter(chunk, RetrievalFilter(section_prefix=("Results",)))


def test_invalid_page_is_explicit() -> None:
    with pytest.raises(RetrievalError) as exc:
        RetrievalFilter(page=0)
    assert exc.value.code == "invalid_filter"
