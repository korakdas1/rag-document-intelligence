from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.context.format import estimated_tokens
from research_assistant.core.errors import ContextError
from research_assistant.core.settings import Settings
from research_assistant.retrieval.models import RetrievalHit


def _settings(**kwargs) -> Settings:
    values = dict(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
        max_context_tokens=256,
        reranker_model_name="overlap",
    )
    values.update(kwargs)
    return Settings(**values)


def _hit(**kwargs) -> RetrievalHit:
    values = dict(
        chunk_id="c1",
        document_id="d1",
        rank=3,
        score=0.2,
        retriever="hybrid",
        text="Self-attention relates distant tokens.",
        page_start=4,
        page_end=5,
        section_path=("Architecture", "Self-Attention"),
        chunker_id="chunker.v1",
        index_id="idx",
        embedding_model_id="emb",
        filename="paper.pdf",
        content_hash="h1",
        rerank_score=1.5,
        rerank_rank=1,
        reranker_id="overlap.v1:x",
    )
    values.update(kwargs)
    return RetrievalHit(**values)


def test_citation_labels_are_deterministic_and_unique() -> None:
    builder = CitationAwareContextBuilder(_settings())
    hits = [
        _hit(chunk_id="a", document_id="d1", filename="a.pdf", content_hash="ha"),
        _hit(chunk_id="b", document_id="d2", filename="b.md", content_hash="hb", page_start=None, page_end=None, section_path=()),
    ]
    first = builder.build(hits, query="q")
    second = builder.build(hits, query="q")
    assert [item.citation_id for item in first.items] == ["S1", "S2"]
    assert [item.citation_id for item in second.items] == ["S1", "S2"]
    assert first.rendered_text == second.rendered_text
    mapping = {item.citation_id: item.source.chunk_id for item in first.items}
    assert mapping == {"S1": "a", "S2": "b"}


def test_filename_and_page_range_preserved() -> None:
    bundle = CitationAwareContextBuilder(_settings()).build([_hit()])
    item = bundle.items[0]
    assert item.source.filename == "paper.pdf"
    assert item.source.page_start == 4
    assert item.source.page_end == 5
    assert "Pages: 4–5" in bundle.rendered_text
    assert "paper.pdf" in bundle.rendered_text
    assert item.source.compact_locator() == 'paper.pdf, pp. 4–5, section "Architecture > Self-Attention"'


def test_null_page_and_empty_section_are_honest() -> None:
    hit = _hit(
        filename="notes.txt",
        page_start=None,
        page_end=None,
        section_path=(),
    )
    rendered = CitationAwareContextBuilder(_settings()).build([hit]).rendered_text
    assert "Pages:" not in rendered
    assert "Section:" not in rendered
    assert "notes.txt" in rendered
    assert "p." not in rendered


def test_empty_filename_uses_document_id_not_a_fake_name() -> None:
    hit = _hit(filename="", document_id="doc-real-id")
    rendered = CitationAwareContextBuilder(_settings()).build([hit]).rendered_text
    assert "doc-real-id" in rendered
    assert "untitled" not in rendered.lower()


def test_multiple_documents_are_kept() -> None:
    hits = [
        _hit(chunk_id="a", document_id="paper", filename="paper.pdf", content_hash="1"),
        _hit(chunk_id="b", document_id="notes", filename="notes.md", content_hash="2", page_start=None, page_end=None, section_path=("Experiments",)),
    ]
    bundle = CitationAwareContextBuilder(_settings()).build(hits)
    assert bundle.diagnostics.source_document_count == 2
    assert {item.source.document_id for item in bundle.items} == {"paper", "notes"}
    assert "Section: Experiments" in bundle.rendered_text


def test_rerank_order_is_respected() -> None:
    hits = [
        _hit(chunk_id="late", rank=1, text="first-stage winner", content_hash="1"),
        _hit(chunk_id="early", rank=4, text="rerank winner", content_hash="2"),
    ]
    bundle = CitationAwareContextBuilder(_settings()).build(hits)
    assert [item.source.chunk_id for item in bundle.items] == ["late", "early"]
    assert bundle.items[0].citation_id == "S1"
    assert bundle.items[0].retrieval_rank == 1


def test_budget_includes_formatting_and_is_enforced() -> None:
    long_hit = _hit(text="evidence token " * 80, content_hash="long")
    short_hit = _hit(
        chunk_id="c2",
        document_id="d2",
        text="tiny",
        content_hash="short",
        filename="other.md",
        page_start=None,
        page_end=None,
        section_path=(),
    )
    bundle = CitationAwareContextBuilder(_settings(max_context_tokens=40)).build(
        [long_hit, short_hit]
    )
    assert bundle.diagnostics.estimated_tokens <= 40
    assert estimated_tokens(bundle.rendered_text) == bundle.diagnostics.estimated_tokens
    assert bundle.diagnostics.estimated_tokens > estimated_tokens(long_hit.text[:20])


def test_oversized_first_item_is_truncated_not_stored_mutated() -> None:
    original = "Self-attention " * 200
    hit = _hit(text=original)
    bundle = CitationAwareContextBuilder(_settings(max_context_tokens=30)).build([hit])
    assert bundle.items
    assert bundle.items[0].truncated is True
    assert bundle.diagnostics.truncated_count == 1
    assert len(bundle.items[0].text) < len(original)
    assert hit.text == original
    assert bundle.diagnostics.estimated_tokens <= 30
    assert original not in bundle.rendered_text or bundle.items[0].text != original


def test_duplicate_chunk_id_skipped() -> None:
    hits = [_hit(chunk_id="same", text="one"), _hit(chunk_id="same", text="two")]
    bundle = CitationAwareContextBuilder(_settings()).build(hits)
    assert bundle.diagnostics.selected_count == 1
    assert bundle.diagnostics.duplicate_count == 1
    assert bundle.items[0].text == "one"


def test_same_content_hash_in_document_is_redundant() -> None:
    hits = [
        _hit(chunk_id="c1", content_hash="dup", text="hello world"),
        _hit(chunk_id="c2", content_hash="dup", text="hello world"),
    ]
    bundle = CitationAwareContextBuilder(_settings()).build(hits)
    assert [item.source.chunk_id for item in bundle.items] == ["c1"]
    assert bundle.diagnostics.redundant_count == 1


def test_overlapping_different_hashes_are_kept() -> None:
    hits = [
        _hit(chunk_id="c1", content_hash="h1", text="alpha beta gamma"),
        _hit(chunk_id="c2", content_hash="h2", text="beta gamma delta"),
    ]
    bundle = CitationAwareContextBuilder(_settings()).build(hits)
    assert [item.source.chunk_id for item in bundle.items] == ["c1", "c2"]


def test_budget_miss_stops_and_records_skip() -> None:
    first = _hit(text="x" * 400, content_hash="1")
    second = _hit(chunk_id="c2", document_id="d2", text="short extra", content_hash="2", filename="b.txt")
    bundle = CitationAwareContextBuilder(_settings(max_context_tokens=25)).build(
        [first, second]
    )
    assert "c2" not in {item.source.chunk_id for item in bundle.items}
    assert bundle.diagnostics.skipped_budget_count >= 1
    assert "c2" in bundle.diagnostics.skipped_chunk_ids
    decisions = {
        item.chunk_id: item
        for item in bundle.diagnostics.selection_decisions
    }
    assert decisions["c1"].selected is True
    assert decisions["c1"].tokens_used_before == 0
    assert decisions["c1"].candidate_tokens is not None
    assert decisions["c2"].reason in {
        "context_budget",
        "after_context_budget_cutoff",
    }


def test_context_decision_records_position_and_token_cost() -> None:
    first = _hit(chunk_id="a", content_hash="a", text="alpha evidence")
    second = _hit(
        chunk_id="b",
        document_id="d2",
        filename="b.md",
        content_hash="b",
        text="beta evidence",
    )
    bundle = CitationAwareContextBuilder(_settings()).build([first, second])
    first_decision, second_decision = bundle.diagnostics.selection_decisions
    assert first_decision.selected is True
    assert first_decision.context_position == 1
    assert first_decision.tokens_added > 0
    assert second_decision.context_position == 2
    assert second_decision.tokens_used_before == first_decision.tokens_added


def test_rendered_context_matches_structured_items() -> None:
    hits = [
        _hit(chunk_id="a", filename="a.pdf", content_hash="a"),
        _hit(chunk_id="b", document_id="d2", filename="b.md", content_hash="b", page_start=None, page_end=None, section_path=()),
    ]
    bundle = CitationAwareContextBuilder(_settings()).build(hits)
    for item in bundle.items:
        assert f"[{item.citation_id}]" in bundle.rendered_text
        assert item.text in bundle.rendered_text
        if item.source.filename:
            assert item.source.filename in bundle.rendered_text


def test_no_invented_provenance() -> None:
    hit = _hit(filename="real.md", page_start=None, page_end=None, section_path=())
    rendered = CitationAwareContextBuilder(_settings()).build([hit]).rendered_text
    assert "page 1" not in rendered.lower()
    assert "Introduction" not in rendered
    assert "real.md" in rendered


def test_invalid_budget() -> None:
    try:
        CitationAwareContextBuilder(_settings()).build([_hit()], max_tokens=0)
    except ContextError as exc:
        assert exc.code == "invalid_budget"
    else:
        raise AssertionError("expected invalid_budget")
