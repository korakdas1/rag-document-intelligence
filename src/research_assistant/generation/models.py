"""Runtime generation types. Not persisted. Never include secrets."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from research_assistant.context.models import CitationSource
from research_assistant.generation.identity import LLMIdentity


class ValidationStatus(StrEnum):
    VALID = "valid"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INVALID_CITATION = "invalid_citation"
    MISSING_CITATIONS = "missing_citations"
    MALFORMED_OUTPUT = "malformed_output"


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class LLMRequest:
    messages: tuple[ChatMessage, ...]
    identity: LLMIdentity
    allowed_citation_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": [message.to_dict() for message in self.messages],
            "identity": self.identity.to_dict(),
            "allowed_citation_ids": list(self.allowed_citation_ids),
        }


@dataclass(frozen=True)
class LLMResponse:
    text: str
    finish_reason: str | None = None
    output_tokens: int | None = None
    input_tokens: int | None = None
    provider_request_id: str | None = None
    generation_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "finish_reason": self.finish_reason,
            "output_tokens": self.output_tokens,
            "input_tokens": self.input_tokens,
            "provider_request_id": self.provider_request_id,
            "generation_ms": round(self.generation_ms, 2),
        }


@dataclass(frozen=True)
class AnswerCitation:
    citation_id: str
    source: CitationSource
    occurrence_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "occurrence_count": self.occurrence_count,
            "source": self.source.to_dict(),
        }


@dataclass(frozen=True)
class GenerationDiagnostics:
    llm_id: str
    provider: str
    model_name: str
    generation_ms: float
    estimated_input_tokens: int
    provider_input_tokens: int | None
    provider_output_tokens: int | None
    finish_reason: str | None
    citation_count: int
    invalid_citation_ids: tuple[str, ...]
    malformed_markers: tuple[str, ...]
    repair_attempts: int
    insufficient_evidence: bool
    empty_context_short_circuit: bool
    provider_request_id: str | None
    validation_status: str
    parsed_inline_citation_ids: tuple[str, ...] = ()
    validated_citation_ids: tuple[str, ...] = ()
    structured_citation_ids: tuple[str, ...] = ()
    prompt_version: str = ""
    parser_version: str = ""
    generation_protocol_status: str = ""
    parser_mode: str = ""
    normalization_applied: tuple[str, ...] = ()
    raw_output_category: str = ""
    format_repair_attempted: bool = False
    format_repair_succeeded: bool = False
    unresolved_referent_short_circuit: bool = False
    first_pass_validation_status: str = ""
    first_pass_answer_text: str = ""
    first_pass_generation_ms: float = 0.0
    repair_ms: float = 0.0
    citation_repair_accepted: bool = False
    citation_repair_rejection_reason: str = ""
    citation_repair_content_preserved: bool | None = None
    citation_repair_input_tokens: int | None = None
    citation_repair_output_tokens: int | None = None
    claim_sources: tuple[tuple[str, tuple[str, ...]], ...] = ()
    sources_disagree: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "llm_id": self.llm_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "generation_ms": round(self.generation_ms, 2),
            "estimated_input_tokens": self.estimated_input_tokens,
            "provider_input_tokens": self.provider_input_tokens,
            "provider_output_tokens": self.provider_output_tokens,
            "finish_reason": self.finish_reason,
            "citation_count": self.citation_count,
            "invalid_citation_ids": list(self.invalid_citation_ids),
            "malformed_markers": list(self.malformed_markers),
            "repair_attempts": self.repair_attempts,
            "insufficient_evidence": self.insufficient_evidence,
            "empty_context_short_circuit": self.empty_context_short_circuit,
            "provider_request_id": self.provider_request_id,
            "validation_status": self.validation_status,
            "parsed_inline_citation_ids": list(self.parsed_inline_citation_ids),
            "validated_citation_ids": list(self.validated_citation_ids),
            "structured_citation_ids": list(self.structured_citation_ids),
            "prompt_version": self.prompt_version,
            "parser_version": self.parser_version,
            "generation_protocol_status": self.generation_protocol_status,
            "parser_mode": self.parser_mode,
            "normalization_applied": list(self.normalization_applied),
            "raw_output_category": self.raw_output_category,
            "format_repair_attempted": self.format_repair_attempted,
            "format_repair_succeeded": self.format_repair_succeeded,
            "unresolved_referent_short_circuit": self.unresolved_referent_short_circuit,
            "first_pass_validation_status": self.first_pass_validation_status,
            "first_pass_answer_text": self.first_pass_answer_text,
            "first_pass_generation_ms": round(self.first_pass_generation_ms, 2),
            "repair_ms": round(self.repair_ms, 2),
            "citation_repair_accepted": self.citation_repair_accepted,
            "citation_repair_rejection_reason": self.citation_repair_rejection_reason,
            "citation_repair_content_preserved": self.citation_repair_content_preserved,
            "citation_repair_input_tokens": self.citation_repair_input_tokens,
            "citation_repair_output_tokens": self.citation_repair_output_tokens,
            "claim_sources": [
                {"claim": claim, "source_ids": list(ids)} for claim, ids in self.claim_sources
            ],
            "sources_disagree": self.sources_disagree,
        }


@dataclass(frozen=True)
class GroundedAnswer:
    question: str
    answer_text: str
    citations: tuple[AnswerCitation, ...]
    invalid_citation_ids: tuple[str, ...]
    insufficient_evidence: bool
    validation_status: ValidationStatus
    diagnostics: GenerationDiagnostics
    raw_response: str = ""

    @property
    def ok(self) -> bool:
        return self.validation_status in {
            ValidationStatus.VALID,
            ValidationStatus.INSUFFICIENT_EVIDENCE,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer_text": self.answer_text,
            "citations": [item.to_dict() for item in self.citations],
            "invalid_citation_ids": list(self.invalid_citation_ids),
            "insufficient_evidence": self.insufficient_evidence,
            "validation_status": self.validation_status.value,
            "ok": self.ok,
            "diagnostics": self.diagnostics.to_dict(),
        }
