import json

from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.core.errors import GenerationError
from research_assistant.core.settings import Settings
from research_assistant.generation.models import ValidationStatus
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.generation.service import EMPTY_CONTEXT_ANSWER, GroundedGenerationService
from research_assistant.retrieval.models import RetrievalHit


def _settings() -> Settings:
    return Settings(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
        reranker_model_name="overlap",
        llm_provider="scripted",
        llm_model_name="scripted.v1",
        llm_citation_repair=False,
    )


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


def _bundle(*hits):
    return CitationAwareContextBuilder(_settings()).build(hits, query="q")


def _json(answer: str, insufficient: bool = False) -> str:
    return json.dumps({"answer": answer, "insufficient_evidence": insufficient})


def test_valid_grounded_answer() -> None:
    llm = ScriptedLLM(_json("Self-attention connects token representations [S1]."))
    service = GroundedGenerationService(_settings(), llm=llm)
    result = service.generate("What is self-attention?", _bundle(_hit()))
    assert result.ok
    assert result.validation_status is ValidationStatus.VALID
    assert "[S1]" in result.answer_text
    assert result.citations[0].source.chunk_id == "c1"
    assert result.diagnostics.parsed_inline_citation_ids == ("S1",)
    assert result.diagnostics.validated_citation_ids == ("S1",)
    assert result.diagnostics.structured_citation_ids == ()
    assert result.diagnostics.llm_id
    assert "api_key" not in result.diagnostics.to_dict()
    assert "Authorization" not in str(result.diagnostics.to_dict())


def test_multi_source_answer() -> None:
    hits = [
        _hit(chunk_id="a", content_hash="a", filename="arch.pdf"),
        _hit(
            chunk_id="b",
            document_id="d2",
            content_hash="b",
            filename="eval.md",
            page_start=None,
            page_end=None,
            section_path=("Evaluation",),
            text="BLEU is reported on WMT.",
        ),
    ]
    llm = ScriptedLLM(_json("Architecture uses attention [S1]. Evaluation uses BLEU [S2]."))
    result = GroundedGenerationService(_settings(), llm=llm).generate("summarize", _bundle(*hits))
    assert {item.citation_id for item in result.citations} == {"S1", "S2"}
    assert result.citations[0].source.filename == "arch.pdf"
    assert result.citations[1].source.filename == "eval.md"


def test_insufficient_evidence_from_model() -> None:
    llm = ScriptedLLM(_json("Not enough support in the documents.", insufficient=True))
    result = GroundedGenerationService(_settings(), llm=llm).generate(
        "When was the moon colonized?", _bundle(_hit())
    )
    assert result.ok
    assert result.insufficient_evidence is True
    assert result.validation_status is ValidationStatus.INSUFFICIENT_EVIDENCE


def test_empty_context_bypasses_llm() -> None:
    def boom(_request):
        raise AssertionError("LLM should not be called for empty context")

    llm = ScriptedLLM(boom)
    empty = CitationAwareContextBuilder(_settings()).build([], query="q")
    result = GroundedGenerationService(_settings(), llm=llm).generate("anything?", empty)
    assert result.diagnostics.empty_context_short_circuit is True
    assert result.insufficient_evidence is True
    assert result.answer_text == EMPTY_CONTEXT_ANSWER
    assert llm.requests == []


def test_invalid_citation_is_not_mapped() -> None:
    llm = ScriptedLLM(_json("Unsupported claim [S99]."))
    result = GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle(_hit()))
    assert result.ok is False
    assert result.validation_status is ValidationStatus.INVALID_CITATION
    assert result.invalid_citation_ids == ("S99",)
    assert result.citations == ()
    assert "[S99]" in result.answer_text


def test_malformed_provider_response() -> None:
    llm = ScriptedLLM("this is not json")
    result = GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle(_hit()))
    assert result.validation_status is ValidationStatus.MALFORMED_OUTPUT
    assert result.ok is False
    assert result.diagnostics.raw_output_category == "malformed_json"
    assert result.diagnostics.format_repair_attempted is False


def test_bare_insufficient_recovers_without_repair() -> None:
    llm = ScriptedLLM("insufficient_evidence=true")
    result = GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle(_hit()))
    assert result.validation_status is ValidationStatus.INSUFFICIENT_EVIDENCE
    assert result.ok is True
    assert result.diagnostics.raw_output_category == "bare_key_value"
    assert result.diagnostics.format_repair_attempted is False
    assert len(llm.requests) == 1


def test_format_repair_disabled_leaves_malformed() -> None:
    llm = ScriptedLLM("just prose")
    result = GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle(_hit()))
    assert result.validation_status is ValidationStatus.MALFORMED_OUTPUT
    assert len(llm.requests) == 1


def test_format_repair_one_attempt_without_evidence() -> None:
    settings = Settings(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
        reranker_model_name="overlap",
        llm_provider="scripted",
        llm_model_name="scripted.v1",
        llm_format_repair=True,
        llm_citation_repair=False,
    )
    llm = ScriptedLLM(
        (
            "not json at all",
            _json("The documents do not provide enough evidence.", insufficient=True),
        )
    )
    result = GroundedGenerationService(settings, llm=llm).generate("q", _bundle(_hit()))
    assert result.validation_status is ValidationStatus.INSUFFICIENT_EVIDENCE
    assert result.diagnostics.format_repair_attempted is True
    assert result.diagnostics.format_repair_succeeded is True
    assert len(llm.requests) == 2
    repair_blob = " ".join(message.content for message in llm.requests[1].messages)
    assert "<evidence>" not in repair_blob
    assert "Self-attention" not in repair_blob


def test_format_repair_does_not_invent_citations() -> None:
    settings = Settings(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
        reranker_model_name="overlap",
        llm_provider="scripted",
        llm_model_name="scripted.v1",
        llm_format_repair=True,
        llm_citation_repair=False,
    )
    llm = ScriptedLLM(
        (
            "not json",
            _json("The answer is X."),
        )
    )
    result = GroundedGenerationService(settings, llm=llm).generate("q", _bundle(_hit()))
    assert result.validation_status is ValidationStatus.MISSING_CITATIONS
    assert "[S1]" not in result.answer_text
    assert result.ok is False


def test_missing_citations_remain_unverified_after_normalization() -> None:
    llm = ScriptedLLM(
        '```json\n{"answer": "The answer is X.", "insufficient_evidence": false}\n```'
    )
    result = GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle(_hit()))
    assert result.validation_status is ValidationStatus.MISSING_CITATIONS
    assert result.diagnostics.raw_output_category == "fenced_json"


def test_provider_failure() -> None:
    llm = ScriptedLLM(error=GenerationError("down", code="provider_unavailable"))
    try:
        GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle(_hit()))
    except GenerationError as exc:
        assert exc.code == "provider_unavailable"
    else:
        raise AssertionError("expected provider_unavailable")


def test_empty_query() -> None:
    try:
        GroundedGenerationService(_settings(), llm=ScriptedLLM()).generate("  ", _bundle(_hit()))
    except GenerationError as exc:
        assert exc.code == "empty_query"
    else:
        raise AssertionError("expected empty_query")


def test_timeout_code_is_distinct() -> None:
    llm = ScriptedLLM(error=GenerationError("timed out", code="timeout"))
    try:
        GroundedGenerationService(_settings(), llm=llm).generate("q", _bundle(_hit()))
    except GenerationError as exc:
        assert exc.code == "timeout"
    else:
        raise AssertionError("expected timeout")


def test_missing_citations_are_not_auto_filled() -> None:
    llm = ScriptedLLM(_json("Self-attention connects token representations."))
    result = GroundedGenerationService(_settings(), llm=llm).generate(
        "What is self-attention?", _bundle(_hit())
    )
    assert result.validation_status is ValidationStatus.MISSING_CITATIONS
    assert result.citations == ()
    assert "[S1]" not in result.answer_text
    assert result.diagnostics.repair_attempts == 0
    assert result.diagnostics.parsed_inline_citation_ids == ()
    assert result.diagnostics.validated_citation_ids == ()
    assert len(llm.requests) == 1


def test_structured_citation_field_is_not_injected_into_answer() -> None:
    llm = ScriptedLLM(
        json.dumps(
            {
                "answer": "Self-attention connects token representations.",
                "citation_ids": ["S1"],
                "insufficient_evidence": False,
            }
        )
    )
    result = GroundedGenerationService(_settings(), llm=llm).generate(
        "What is self-attention?", _bundle(_hit())
    )
    assert result.validation_status is ValidationStatus.MISSING_CITATIONS
    assert "[S1]" not in result.answer_text
    assert result.diagnostics.structured_citation_ids == ("S1",)
    assert result.diagnostics.validated_citation_ids == ()


def test_citation_repair_one_attempt_same_bundle() -> None:
    settings = Settings(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
        reranker_model_name="overlap",
        llm_provider="scripted",
        llm_model_name="scripted.v1",
        llm_citation_repair=True,
    )
    llm = ScriptedLLM(
        (
            _json("Self-attention connects token representations."),
            _json("Self-attention connects token representations [S1]."),
        )
    )
    result = GroundedGenerationService(settings, llm=llm).generate(
        "What is self-attention?", _bundle(_hit())
    )
    assert result.validation_status is ValidationStatus.VALID
    assert result.diagnostics.repair_attempts == 1
    assert result.diagnostics.first_pass_validation_status == "missing_citations"
    assert "[S1]" not in result.diagnostics.first_pass_answer_text
    assert len(llm.requests) == 2
    assert llm.requests[0].allowed_citation_ids == llm.requests[1].allowed_citation_ids
    assert "[S1]" in result.answer_text


def test_failed_repair_still_fail_closed() -> None:
    settings = Settings(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
        reranker_model_name="overlap",
        llm_provider="scripted",
        llm_model_name="scripted.v1",
        llm_citation_repair=True,
    )
    llm = ScriptedLLM(
        (
            _json("Self-attention connects token representations."),
            _json("Self-attention connects token representations."),
        )
    )
    result = GroundedGenerationService(settings, llm=llm).generate(
        "What is self-attention?", _bundle(_hit())
    )
    assert result.validation_status is ValidationStatus.MISSING_CITATIONS
    assert result.diagnostics.repair_attempts == 1
    assert result.citations == ()
    assert len(llm.requests) == 2


def test_llm_id_excludes_query_and_secrets() -> None:
    identity = GroundedGenerationService(
        _settings(), llm=ScriptedLLM()
    ).identity()
    payload = identity.to_dict()
    assert "api_key" not in payload
    assert "question" not in payload
    assert identity.llm_id == ScriptedLLM().identity.llm_id


def test_product_default_enables_citation_repair_not_auto_attach() -> None:
    from research_assistant.core.settings import DEFAULT_LLM_CITATION_REPAIR

    assert DEFAULT_LLM_CITATION_REPAIR is True


def test_unresolved_referent_does_not_call_llm() -> None:
    llm = ScriptedLLM(_json("The system launched in March [S1]."))
    result = GroundedGenerationService(_settings(), llm=llm).generate(
        "When did it launch?",
        _bundle(_hit()),
        unresolved_referent=True,
    )
    assert result.insufficient_evidence is True
    assert result.diagnostics.unresolved_referent_short_circuit is True
    assert result.citations == ()
    assert llm.requests == []
    assert "March" not in result.answer_text
