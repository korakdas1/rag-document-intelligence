import json
from dataclasses import replace

import pytest

from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.core.settings import Settings
from research_assistant.generation.models import ValidationStatus
from research_assistant.generation.repair import preserves_answer_content, validate_citation_repair
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.generation.service import GroundedGenerationService
from research_assistant.retrieval.models import RetrievalHit


def _settings() -> Settings:
    return Settings(
        database_path="unused.db", log_level="WARNING", max_file_bytes=10,
        llm_provider="scripted", llm_model_name="scripted.v1", llm_citation_repair=True,
    )


def _bundle():
    hit = RetrievalHit(
        chunk_id="c1", document_id="d1", rank=1, score=1.0, retriever="hybrid",
        text="Self-attention connects token representations.", page_start=None,
        page_end=None, section_path=(), chunker_id="test", index_id="test",
        embedding_model_id="test", filename="paper.md", content_hash="test",
    )
    return CitationAwareContextBuilder(_settings()).build([hit])


def _json(answer, flag=False):
    return json.dumps({"answer": answer, "insufficient_evidence": flag}, ensure_ascii=False)


@pytest.mark.parametrize("repaired", [
    "Self-attention connects token representations [S1].",
    "Self-attention connects token representations. [S1]",
    "Self-attention [S1] connects token representations [S1].",
])
def test_marker_only_repair_is_accepted(repaired):
    original = "Self-attention connects token representations."
    llm = ScriptedLLM((_json(original), _json(repaired)))
    result = GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle())
    assert result.answer_text == repaired
    assert result.raw_response == _json(repaired)
    assert result.validation_status is ValidationStatus.VALID
    assert result.insufficient_evidence is False
    assert result.diagnostics.citation_repair_accepted is True
    assert result.diagnostics.citation_repair_content_preserved is True
    assert result.diagnostics.citation_repair_rejection_reason == ""
    assert result.diagnostics.validated_citation_ids == ("S1",)
    assert len(llm.requests) == 2


@pytest.mark.parametrize(("original", "repaired"), [
    ("The project identifier belongs to the pilot is NBP-X.",
     "The project identifier for the pilot is NBP-X [S1]."),
    ("The calibration record key accompanies the amendment is ABC-X.",
     "The calibration record key accompanying the amendment is ABC-X [S1]."),
    ("31 records", "32 records [S1]"),
    ("The system does not collect faces.", "The system collects faces [S1]."),
    ("Alpha", "Beta [S1]"),
    ("Alpha launched.", "Alpha launched and closed [S1]."),
    ("Alpha launched and closed.", "Alpha launched [S1]."),
    ("Alpha launched.", "alpha launched [S1]."),
    ("Alpha launched!", "Alpha launched [S1]."),
    ("Alpha then Beta.", "Beta then Alpha [S1]."),
    ("Alpha  launched.", "Alpha launched [S1]."),
    ("Alpha launched.", "Alpha  launched [S1]."),
    ("Alpha\nlaunched.", "Alpha launched [S1]."),
    ("Alpha launched.", "Alpha launched.\n[S1]"),
    ("Alpha launched.", "Alpha launched.\t[S1]"),
    ("The café launched.", "The cafe\u0301 launched [S1]."),
])
def test_content_changes_rejected_and_original_returned_without_third_call(original, repaired):
    llm = ScriptedLLM((_json(original), _json(repaired), _json("Must never be called [S1].")))
    result = GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle())
    assert result.answer_text == original
    assert result.raw_response == _json(original)
    assert result.validation_status is ValidationStatus.MISSING_CITATIONS
    assert result.insufficient_evidence is False
    assert result.citations == ()
    assert result.invalid_citation_ids == ()
    assert result.diagnostics.repair_attempts == 1
    assert result.diagnostics.citation_repair_accepted is False
    assert result.diagnostics.citation_repair_rejection_reason == "content_changed"
    assert result.diagnostics.citation_repair_content_preserved is False
    assert result.diagnostics.first_pass_answer_text == original
    assert len(llm.requests) == 2


@pytest.mark.parametrize(("raw", "reason"), [
    (_json("Alpha launched [S99]."), "invalid_citation"),
    (_json("Alpha launched [S1] [S99]."), "invalid_citation"),
    (_json("Alpha launched [Sx]."), "invalid_citation"),
    (_json("Alpha launched [S1].", True), "insufficient_flag_changed"),
    (_json("Alpha launched."), "missing_citations_after_repair"),
    ('{"answer":"Alpha launched.","insufficient_evidence":false,"citations":["S1"]}',
     "missing_citations_after_repair"),
    ("not json", "malformed_output"),
    ('{"answer": "Alpha launched [S1]."}', "malformed_output"),
    (_json("Alpha launched [S1].", "false"), "malformed_output"),
    (_json(31), "malformed_output"),
    (_json(""), "malformed_output"),
    ("```json\n" + _json("Alpha launched [S1].") + "\n```", "malformed_output"),
    (_json("Alpha launched [S1].") + _json("Alpha launched [S1]."), "malformed_output"),
    ('{"answer":"Alpha launched [S1].","insufficient_evidence":false,"extra":NaN}',
     "malformed_output"),
    (_json("Alpha\ufeff launched [S1]."), "content_changed"),
])
def test_protocol_failures_preserve_first_pass(raw, reason):
    original = "Alpha launched."
    llm = ScriptedLLM((_json(original), raw))
    result = GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle())
    assert result.answer_text == original
    assert result.raw_response == _json(original)
    assert result.validation_status is ValidationStatus.MISSING_CITATIONS
    assert result.insufficient_evidence is False
    assert result.citations == ()
    diagnostics = result.diagnostics.to_dict()
    assert diagnostics["repair_attempts"] == 1
    assert diagnostics["citation_repair_accepted"] is False
    assert diagnostics["citation_repair_rejection_reason"] == reason
    assert len(llm.requests) == 2


@pytest.mark.parametrize(("original", "repaired", "expected"), [
    ("A. B.", "A. [S1] B. [S2]", True),
    ("A.  B.", "A. [S1] B.", True),
    ("A.   B.", "A. [S1] B.", False),
    ("A.\nB.\tC.", "A. [S1]\nB.\tC.[S2]", True),
    ("A.", " [S1]A. [S1] [S2] ", True),
    (" A. ", " [S1]A. [S2]", True),
    (" A. ", "[S1]A.[S2]", False),
    ("A.", "A. [S0]", False),
    ("A.", "A. [S01]", False),
    ("A.", "A. [S#]", False),
    ("A.", "A.\u00a0[S1]", False),
    ("A.", "A.[S1]\u200b", False),
])
def test_only_marker_adjacent_inserted_spaces_can_be_removed(original, repaired, expected):
    assert preserves_answer_content(original, repaired, ("S1", "S2")) is expected


def test_format_repair_cannot_trigger_a_third_citation_call():
    llm = ScriptedLLM(("not json", _json("Alpha launched."), _json("Alpha launched [S1].")))
    settings = replace(_settings(), llm_format_repair=True)
    result = GroundedGenerationService(settings, llm=llm).generate("q", _bundle())
    assert result.validation_status is ValidationStatus.MISSING_CITATIONS
    assert result.diagnostics.format_repair_attempted is True
    assert result.diagnostics.citation_repair_accepted is False
    assert result.diagnostics.repair_attempts == 0
    assert len(llm.requests) == 2


def test_separate_repair_engine_is_bounded_and_cannot_change_content():
    original = "Alpha launched."
    first = ScriptedLLM(_json(original))
    repair = ScriptedLLM(_json("Beta launched [S1]."))
    result = GroundedGenerationService(_settings(), llm=first, repair_llm=repair).generate("q", _bundle())
    assert result.answer_text == original
    assert len(first.requests) == len(repair.requests) == 1
    assert result.diagnostics.citation_repair_rejection_reason == "content_changed"


def test_no_repair_diagnostics_when_already_cited():
    llm = ScriptedLLM(_json("Alpha launched [S1]."))
    result = GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle())
    assert result.diagnostics.repair_attempts == 0
    assert result.diagnostics.citation_repair_accepted is False
    assert result.diagnostics.citation_repair_rejection_reason == ""
    assert result.diagnostics.citation_repair_content_preserved is None
    assert len(llm.requests) == 1


def test_validator_does_not_treat_missing_markers_as_success():
    result = validate_citation_repair("Alpha launched.", _json("Alpha launched."), _bundle())
    assert result.content_preserved is True
    assert result.accepted is False
    assert result.rejection_reason == "missing_citations_after_repair"
