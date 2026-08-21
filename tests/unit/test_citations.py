from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.core.settings import Settings
from research_assistant.generation.citations import (
    extract_citations,
    parse_model_output,
    render_sources,
    validate_citations,
)
from research_assistant.generation.models import ValidationStatus
from research_assistant.retrieval.models import RetrievalHit


def _bundle(*hits):
    return CitationAwareContextBuilder(
        Settings(
            database_path="unused.db",
            log_level="WARNING",
            max_file_bytes=10,
            reranker_model_name="overlap",
            llm_provider="scripted",
        )
    ).build(hits)


def _hit(**kwargs) -> RetrievalHit:
    values = dict(
        chunk_id="c1",
        document_id="d1",
        rank=1,
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
    )
    values.update(kwargs)
    return RetrievalHit(**values)


def test_extract_single_and_adjacent_citations() -> None:
    extracted = extract_citations("Self-attention relates tokens [S1]. Also [S1][S2].")
    assert extracted.ids == ("S1", "S1", "S2")
    assert extracted.counts["S1"] == 2
    assert extracted.malformed_markers == ()


def test_extract_repeated_and_sentence_end() -> None:
    extracted = extract_citations("Claim one [S1]. Claim two [S1].")
    assert tuple(dict.fromkeys(extracted.ids)) == ("S1",)


def test_malformed_and_non_citation_brackets() -> None:
    extracted = extract_citations("See [S] and [Sabc] and array[0] and [notes].")
    assert extracted.ids == ()
    assert "[S]" in extracted.malformed_markers
    assert "[Sabc]" in extracted.malformed_markers
    assert "[0]" not in extracted.malformed_markers
    assert "[notes]" not in extracted.malformed_markers


def test_no_citation() -> None:
    extracted = extract_citations("There is no marker here.")
    assert extracted.ids == ()


def test_many_citations() -> None:
    text = " ".join(f"[S{i}]" for i in range(1, 12))
    extracted = extract_citations(text)
    assert extracted.ids[0] == "S1"
    assert extracted.ids[-1] == "S11"
    assert len(extracted.ids) == 11


def test_unknown_citation_is_invalid() -> None:
    bundle = _bundle(_hit())
    status, citations, invalid, _ = validate_citations(
        "Unsupported claim [S99].",
        bundle,
        insufficient_evidence=False,
        malformed_output=False,
    )
    assert status is ValidationStatus.INVALID_CITATION
    assert invalid == ("S99",)
    assert citations == ()


def test_valid_citation_maps_to_source() -> None:
    bundle = _bundle(_hit(), _hit(chunk_id="c2", document_id="d2", filename="other.md", content_hash="h2", page_start=None, page_end=None, section_path=()))
    status, citations, invalid, _ = validate_citations(
        "Architecture in [S1] and method in [S2].",
        bundle,
        insufficient_evidence=False,
        malformed_output=False,
    )
    assert status is ValidationStatus.VALID
    assert invalid == ()
    assert citations[0].source.chunk_id == "c1"
    assert citations[1].source.filename == "other.md"
    assert "Pages:" not in citations[1].source.compact_locator()


def test_missing_citations_on_substantive_answer() -> None:
    bundle = _bundle(_hit())
    status, _, _, _ = validate_citations(
        "Transformers definitely use magic.",
        bundle,
        insufficient_evidence=False,
        malformed_output=False,
    )
    assert status is ValidationStatus.MISSING_CITATIONS


def test_insufficient_evidence_does_not_require_citations() -> None:
    bundle = _bundle(_hit())
    status, citations, _, _ = validate_citations(
        "Not enough evidence in the provided documents.",
        bundle,
        insufficient_evidence=True,
        malformed_output=False,
    )
    assert status is ValidationStatus.INSUFFICIENT_EVIDENCE
    assert citations == ()


def test_render_sources_is_honest() -> None:
    bundle = _bundle(_hit())
    _, citations, _, _ = validate_citations(
        "Self-attention [S1].",
        bundle,
        insufficient_evidence=False,
        malformed_output=False,
    )
    rendered = render_sources(citations)
    assert rendered.startswith("[S1] paper.pdf")
    assert "pp. 4–5" in rendered
    assert "Architecture > Self-Attention" in rendered


def test_parse_json_object_and_fence() -> None:
    parsed = parse_model_output(
        '```json\n{"answer": "Hello [S1].", "insufficient_evidence": false}\n```'
    )
    assert parsed.malformed is False
    assert parsed.answer == "Hello [S1]."
    assert parsed.insufficient_evidence is False


def test_parse_malformed_text() -> None:
    parsed = parse_model_output("just prose")
    assert parsed.malformed is True


def test_parse_keeps_inline_citation_inside_answer() -> None:
    parsed = parse_model_output(
        '{"answer": "Alex and Morgan married one year later. [S1]", '
        '"insufficient_evidence": false}'
    )
    assert parsed.malformed is False
    assert "[S1]" in parsed.answer


def test_parse_does_not_promote_sibling_citation_field() -> None:
    parsed = parse_model_output(
        '{"answer": "Alex and Morgan married one year later.", '
        '"citation_ids": ["S1"], "insufficient_evidence": false}'
    )
    assert parsed.malformed is False
    assert "[S1]" not in parsed.answer
    assert parsed.structured_citation_ids == ("S1",)
    status, _, _, _ = validate_citations(
        parsed.answer,
        _bundle(_hit()),
        insufficient_evidence=False,
        malformed_output=False,
    )
    assert status is ValidationStatus.MISSING_CITATIONS


def test_parse_strips_fence_without_dropping_markers() -> None:
    parsed = parse_model_output(
        "```json\n"
        '{"answer": "Alex founded the company [S1].", "insufficient_evidence": false}\n'
        "```"
    )
    assert parsed.answer == "Alex founded the company [S1]."
    assert parsed.raw_output_category == "fenced_json"
    assert parsed.protocol_status == "normalized"


def test_parse_whitespace_and_bom() -> None:
    parsed = parse_model_output(
        '\ufeff  {"answer": "Ready [S1].", "insufficient_evidence": false}  '
    )
    assert parsed.malformed is False
    assert "bom" in parsed.normalization_applied
    assert "whitespace" in parsed.normalization_applied


def test_parse_bare_insufficient_true_recovers() -> None:
    parsed = parse_model_output("insufficient_evidence=true")
    assert parsed.malformed is False
    assert parsed.insufficient_evidence is True
    assert parsed.raw_output_category == "bare_key_value"
    assert parsed.protocol_status == "recovered"
    assert "[S" not in parsed.answer


def test_parse_bare_insufficient_false_is_malformed() -> None:
    parsed = parse_model_output("insufficient_evidence=false")
    assert parsed.malformed is True
    assert parsed.raw_output_category == "bare_key_value"


def test_parse_rejects_leading_prose() -> None:
    parsed = parse_model_output(
        'Note: {"answer": "Hello [S1].", "insufficient_evidence": false}'
    )
    assert parsed.malformed is True
    assert parsed.raw_output_category == "leading_prose"


def test_parse_rejects_trailing_prose() -> None:
    parsed = parse_model_output(
        '{"answer": "Hello [S1].", "insufficient_evidence": false}\nThanks'
    )
    assert parsed.malformed is True
    assert parsed.raw_output_category == "trailing_prose"


def test_parse_rejects_multiple_objects() -> None:
    parsed = parse_model_output(
        '{"answer": "A [S1].", "insufficient_evidence": false}'
        '{"answer": "B [S1].", "insufficient_evidence": false}'
    )
    assert parsed.malformed is True
    assert parsed.raw_output_category == "multiple_objects"


def test_parse_wrong_boolean_type() -> None:
    parsed = parse_model_output(
        '{"answer": "Hello [S1].", "insufficient_evidence": "true"}'
    )
    assert parsed.malformed is True
    assert parsed.raw_output_category == "wrong_type"


def test_parse_missing_flag() -> None:
    parsed = parse_model_output('{"answer": "Hello [S1]."}')
    assert parsed.malformed is True
    assert parsed.raw_output_category == "missing_insufficient_flag"


def test_parse_empty_answer_false_is_malformed() -> None:
    parsed = parse_model_output('{"answer": "  ", "insufficient_evidence": false}')
    assert parsed.malformed is True
    assert parsed.raw_output_category == "missing_answer"


def test_parse_missing_answer_true_recovers() -> None:
    parsed = parse_model_output('{"insufficient_evidence": true}')
    assert parsed.malformed is False
    assert parsed.insufficient_evidence is True
    assert parsed.protocol_status == "recovered"

