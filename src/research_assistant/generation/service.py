"""Grounded generation from a ContextBundle. Does not retrieve or rerank."""

from __future__ import annotations

from research_assistant.context.models import ContextBundle
from research_assistant.core.errors import GenerationError
from research_assistant.core.logging import get_logger
from research_assistant.core.settings import Settings, load_settings
from research_assistant.generation.citations import (
    PARSER_VERSION,
    extract_citations,
    parse_model_output,
    render_sources,
    validate_citations,
)
from research_assistant.generation.factory import llm_from_settings
from research_assistant.generation.identity import LLMIdentity
from research_assistant.generation.models import (
    GenerationDiagnostics,
    GroundedAnswer,
    ValidationStatus,
)
from research_assistant.generation.prompt import (
    PROMPT_VERSION,
    build_format_repair_request,
    build_repair_request,
    build_request,
    estimated_prompt_tokens,
)
from research_assistant.generation.protocol import LLMClient
from research_assistant.generation.repair import validate_citation_repair

logger = get_logger("research_assistant.generation")

EMPTY_CONTEXT_ANSWER = (
    "Insufficient evidence in the provided documents to answer that."
)
UNRESOLVED_REFERENT_ANSWER = (
    "The question does not name which subject is meant, and there is no "
    "conversation context to resolve it."
)


class GroundedGenerationService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        llm: LLMClient | None = None,
        repair_llm: LLMClient | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._llm = llm
        self._repair_llm = repair_llm

    def identity(self) -> LLMIdentity:
        return self._engine().identity

    def generate(
        self,
        question: str,
        bundle: ContextBundle,
        *,
        unresolved_referent: bool = False,
    ) -> GroundedAnswer:
        if not question or not question.strip():
            raise GenerationError("Query text is empty", code="empty_query")
        question = question.strip()
        engine = self._engine()
        identity = engine.identity
        if unresolved_referent:
            return _unresolved_referent_answer(question, identity)
        if not bundle.items:
            return _empty_context_answer(question, identity)

        request = build_request(question, bundle, identity)
        estimated_in = estimated_prompt_tokens(request)
        try:
            response = engine.generate(request)
        except GenerationError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GenerationError(
                f"LLM provider failed: {exc}",
                code="provider_unavailable",
            ) from exc

        parsed = parse_model_output(response.text)
        format_repair_attempted = False
        format_repair_succeeded = False
        if parsed.malformed and self._settings.llm_format_repair:
            format_repair_attempted = True
            repair_request = build_format_repair_request(identity, response.text)
            try:
                repaired_format = engine.generate(repair_request)
            except GenerationError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise GenerationError(
                    f"LLM provider failed: {exc}",
                    code="provider_unavailable",
                ) from exc
            generation_ms = response.generation_ms + repaired_format.generation_ms
            parsed_repair = parse_model_output(repaired_format.text)
            format_repair_succeeded = not parsed_repair.malformed
            if format_repair_succeeded:
                parsed = parsed_repair
                response = repaired_format
        else:
            generation_ms = response.generation_ms

        first_pass_generation_ms = generation_ms
        answer_text = parsed.answer
        status, citations, invalid, malformed = validate_citations(
            answer_text,
            bundle,
            insufficient_evidence=parsed.insufficient_evidence,
            malformed_output=parsed.malformed,
        )
        repair_attempts = 0
        repair_ms = 0.0
        first_pass_status = status.value
        first_pass_answer = answer_text
        repair_accepted = False
        repair_rejection_reason = ""
        repair_content_preserved = None
        repair_input_tokens = None
        repair_output_tokens = None
        if (
            status is ValidationStatus.MISSING_CITATIONS
            and self._settings.llm_citation_repair
            and not format_repair_attempted
        ):
            repair_attempts = 1
            repair_request = build_repair_request(
                bundle, identity, first_pass_answer
            )
            repair_engine = self._repair_engine()
            try:
                repaired = repair_engine.generate(repair_request)
            except GenerationError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise GenerationError(
                    f"LLM provider failed: {exc}",
                    code="provider_unavailable",
                ) from exc
            repair_ms = repaired.generation_ms
            generation_ms += repair_ms
            repair_input_tokens = repaired.input_tokens
            repair_output_tokens = repaired.output_tokens
            repair_validation = validate_citation_repair(
                first_pass_answer, repaired.text, bundle
            )
            repair_accepted = repair_validation.accepted
            repair_rejection_reason = repair_validation.rejection_reason
            repair_content_preserved = repair_validation.content_preserved
            if repair_accepted:
                parsed = repair_validation.parsed
                answer_text = parsed.answer
                status, citations, invalid, malformed = validate_citations(
                    answer_text,
                    bundle,
                    insufficient_evidence=parsed.insufficient_evidence,
                    malformed_output=parsed.malformed,
                )
                response = repaired
        diagnostics = GenerationDiagnostics(
            llm_id=identity.llm_id,
            provider=identity.provider,
            model_name=identity.model_name,
            generation_ms=generation_ms,
            estimated_input_tokens=estimated_in,
            provider_input_tokens=response.input_tokens,
            provider_output_tokens=response.output_tokens,
            finish_reason=response.finish_reason,
            citation_count=len(citations),
            invalid_citation_ids=invalid,
            malformed_markers=malformed,
            repair_attempts=repair_attempts,
            insufficient_evidence=parsed.insufficient_evidence
            or status is ValidationStatus.INSUFFICIENT_EVIDENCE,
            empty_context_short_circuit=False,
            provider_request_id=response.provider_request_id,
            validation_status=status.value,
            parsed_inline_citation_ids=tuple(
                dict.fromkeys(extract_citations(answer_text).ids)
            ),
            validated_citation_ids=tuple(item.citation_id for item in citations),
            structured_citation_ids=parsed.structured_citation_ids,
            prompt_version=PROMPT_VERSION,
            parser_version=PARSER_VERSION,
            generation_protocol_status=parsed.protocol_status,
            parser_mode=PARSER_VERSION,
            normalization_applied=parsed.normalization_applied,
            raw_output_category=parsed.raw_output_category,
            format_repair_attempted=format_repair_attempted,
            format_repair_succeeded=format_repair_succeeded,
            first_pass_validation_status=first_pass_status if repair_attempts else "",
            first_pass_answer_text=first_pass_answer if repair_attempts else "",
            first_pass_generation_ms=first_pass_generation_ms,
            repair_ms=repair_ms,
            citation_repair_accepted=repair_accepted,
            citation_repair_rejection_reason=repair_rejection_reason,
            citation_repair_content_preserved=repair_content_preserved,
            citation_repair_input_tokens=repair_input_tokens,
            citation_repair_output_tokens=repair_output_tokens,
            claim_sources=parsed.claim_sources,
            sources_disagree=parsed.sources_disagree,
        )
        logger.info(
            "generation_completed status=%s protocol=%s category=%s citations=%s invalid=%s "
            "ms=%.1f first_pass_ms=%.1f repair_ms=%.1f repair=%s "
            "repair_accepted=%s repair_rejection=%s",
            status.value,
            parsed.protocol_status,
            parsed.raw_output_category,
            len(citations),
            len(invalid),
            diagnostics.generation_ms,
            first_pass_generation_ms,
            repair_ms,
            repair_attempts,
            repair_accepted,
            repair_rejection_reason,
        )
        return GroundedAnswer(
            question=question,
            answer_text=answer_text,
            citations=citations,
            invalid_citation_ids=invalid,
            insufficient_evidence=diagnostics.insufficient_evidence,
            validation_status=status,
            diagnostics=diagnostics,
            raw_response=response.text,
        )

    def _engine(self) -> LLMClient:
        if self._llm is None:
            self._llm = llm_from_settings(self._settings)
        return self._llm

    def _repair_engine(self) -> LLMClient:
        if self._repair_llm is not None:
            return self._repair_llm
        repair_name = self._settings.llm_repair_model_name.strip()
        if not repair_name or repair_name == self._settings.llm_model_name.strip():
            return self._engine()
        self._repair_llm = llm_from_settings(self._settings, model_name=repair_name)
        return self._repair_llm


def render_answer(answer: GroundedAnswer) -> str:
    sources = render_sources(answer.citations)
    parts = [answer.answer_text.strip()]
    if sources:
        parts.extend(["", "Sources:", sources])
    return "\n".join(parts).strip()


def _unresolved_referent_answer(question: str, identity: LLMIdentity) -> GroundedAnswer:
    diagnostics = GenerationDiagnostics(
        llm_id=identity.llm_id,
        provider=identity.provider,
        model_name=identity.model_name,
        generation_ms=0.0,
        estimated_input_tokens=0,
        provider_input_tokens=None,
        provider_output_tokens=None,
        finish_reason=None,
        citation_count=0,
        invalid_citation_ids=(),
        malformed_markers=(),
        repair_attempts=0,
        insufficient_evidence=True,
        empty_context_short_circuit=False,
        provider_request_id=None,
        validation_status=ValidationStatus.INSUFFICIENT_EVIDENCE.value,
        unresolved_referent_short_circuit=True,
    )
    return GroundedAnswer(
        question=question,
        answer_text=UNRESOLVED_REFERENT_ANSWER,
        citations=(),
        invalid_citation_ids=(),
        insufficient_evidence=True,
        validation_status=ValidationStatus.INSUFFICIENT_EVIDENCE,
        diagnostics=diagnostics,
        raw_response="",
    )


def _empty_context_answer(question: str, identity: LLMIdentity) -> GroundedAnswer:
    diagnostics = GenerationDiagnostics(
        llm_id=identity.llm_id,
        provider=identity.provider,
        model_name=identity.model_name,
        generation_ms=0.0,
        estimated_input_tokens=0,
        provider_input_tokens=None,
        provider_output_tokens=None,
        finish_reason=None,
        citation_count=0,
        invalid_citation_ids=(),
        malformed_markers=(),
        repair_attempts=0,
        insufficient_evidence=True,
        empty_context_short_circuit=True,
        provider_request_id=None,
        validation_status=ValidationStatus.INSUFFICIENT_EVIDENCE.value,
    )
    return GroundedAnswer(
        question=question,
        answer_text=EMPTY_CONTEXT_ANSWER,
        citations=(),
        invalid_citation_ids=(),
        insufficient_evidence=True,
        validation_status=ValidationStatus.INSUFFICIENT_EVIDENCE,
        diagnostics=diagnostics,
        raw_response="",
    )
