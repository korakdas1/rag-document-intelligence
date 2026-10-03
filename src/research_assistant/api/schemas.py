"""API DTOs. Distinct from domain models; mapping stays thin."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RetrievalModeName = Literal["hybrid", "dense", "lexical"]
DocumentStatusName = Literal["failed", "parsed", "chunked", "ready"]
GroundingStatusName = Literal[
    "grounded",
    "insufficient_evidence",
    "unverified",
    "invalid_citation",
    "malformed_output",
]


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str = ""
    turn_id: str | None = None
    session_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ComponentHealth(BaseModel):
    status: Literal["ok", "unavailable", "not_configured", "configured"]
    detail: str = ""


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    service: str = "research-assistant"
    request_id: str = ""


class ReadyResponse(BaseModel):
    status: Literal["ready", "degraded", "not_ready"]
    database: ComponentHealth
    vector_store: ComponentHealth
    llm_provider: ComponentHealth
    embedding: ComponentHealth
    request_id: str = ""


class HealthResponse(LivenessResponse):
    """Process liveness. Dependency checks live on GET /ready."""


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    content_type: str
    status: DocumentStatusName
    page_count: int | None = None
    chunk_count: int = 0
    byte_size: int = 0
    warning_count: int = 0
    ingested_at: str
    updated_at: str
    parse_status: str
    error_message: str | None = None
    source_available: bool = True
    checksum_prefix: str = ""


class DocumentDetail(DocumentSummary):
    chunker_id: str
    parser_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
    checksum_sha256: str = ""
    index_status: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]
    chunker_id: str
    request_id: str = ""


class UploadResponse(BaseModel):
    document: DocumentSummary
    outcome: str
    warnings: list[str] = Field(default_factory=list)
    request_id: str = ""


class DeleteDocumentResponse(BaseModel):
    document_id: str
    deleted: bool
    already_absent: bool = False
    vector_cleanup_status: str
    request_id: str = ""


class ConversationTurnView(BaseModel):
    question: str
    answer: str
    grounding_status: str = ""


class AskRequest(BaseModel):
    question: str
    document_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Without a session, omitted/empty IDs search all ready documents. With a session, "
            "omit this field to use saved scope; supplied IDs must match its effective documents."
        ),
    )
    retrieval_mode: RetrievalModeName = "hybrid"
    rerank: bool | None = None
    conversation: list[ConversationTurnView] = Field(default_factory=list)
    session_id: str | None = None
    replace_turn_id: str | None = None


class SourceView(BaseModel):
    citation_id: str
    filename: str
    document_id: str
    page_start: int | None = None
    page_end: int | None = None
    section_path: list[str] = Field(default_factory=list)
    locator: str
    text: str
    truncated: bool = False
    cited_by_model: bool = False


class CitationView(BaseModel):
    citation_id: str
    filename: str
    document_id: str
    page_start: int | None = None
    page_end: int | None = None
    section_path: list[str] = Field(default_factory=list)
    locator: str
    occurrence_count: int = 1


class CandidateView(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    rank: int
    page_start: int | None = None
    page_end: int | None = None
    section_path: list[str] = Field(default_factory=list)
    dense_rank: int | None = None
    lexical_rank: int | None = None
    rerank_rank: int | None = None
    retrievers: list[str] = Field(default_factory=list)
    rerank_score: float | None = None
    selected_in_context: bool = False
    context_position: int | None = None
    score_note: str = "Scores are uncalibrated (not relevance percentages)."


class DiagnosticsView(BaseModel):
    retrieval_mode: str
    rerank_enabled: bool
    candidate_count: int
    context_source_count: int
    dense_ms: float | None = None
    lexical_ms: float | None = None
    fusion_ms: float | None = None
    retrieval_ms: float | None = None
    rerank_ms: float | None = None
    generation_ms: float | None = None
    first_pass_generation_ms: float | None = None
    repair_ms: float | None = None
    llm_id: str | None = None
    reranker_id: str | None = None
    validation_status: str
    candidates: list[CandidateView] = Field(default_factory=list)
    original_question: str | None = None
    retrieval_query: str | None = None
    rewrite_applied: bool = False
    followup_detected: bool = False
    ambiguous_followup: bool = False
    history_turns_used: int = 0
    resolver_id: str | None = None
    resolver_method: str | None = None
    resolver_ms: float | None = None
    conversation_subjects: list[str] = Field(default_factory=list)
    repair_attempts: int = 0
    generation_question: str | None = None
    context_citation_ids: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False
    parsed_inline_citation_ids: list[str] = Field(default_factory=list)
    validated_citation_ids: list[str] = Field(default_factory=list)
    structured_citation_ids: list[str] = Field(default_factory=list)
    prompt_version: str | None = None
    parser_version: str | None = None
    generation_protocol_status: str | None = None
    parser_mode: str | None = None
    normalization_applied: list[str] = Field(default_factory=list)
    raw_output_category: str | None = None
    format_repair_attempted: bool = False
    format_repair_succeeded: bool = False


class AskResponse(BaseModel):
    question: str
    answer: str
    grounding_status: GroundingStatusName
    validation_status: str
    insufficient_evidence: bool
    citations: list[CitationView]
    sources: list[SourceView]
    diagnostics: DiagnosticsView
    request_id: str = ""
    session_id: str | None = None
    turn_id: str | None = None


class SessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    turn_count: int = 0
    all_documents: bool = True


class SessionTurnView(BaseModel):
    turn_id: str
    sequence: int
    question: str
    answer: str
    grounding_status: str
    validation_status: str | None = None
    insufficient_evidence: bool = False
    error_message: str | None = None
    original_question: str | None = None
    retrieval_query: str | None = None
    generation_question: str | None = None
    citations: list[CitationView] = Field(default_factory=list)
    sources: list[SourceView] = Field(default_factory=list)
    diagnostics: DiagnosticsView | None = None
    created_at: str


class SessionDetail(SessionSummary):
    selected_document_ids: list[str] = Field(
        default_factory=list,
        description="Saved selection, including IDs deleted since it was saved; empty for ALL/NONE.",
    )
    missing_selected_count: int = 0
    turns: list[SessionTurnView] = Field(default_factory=list)


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
    request_id: str = ""


class CreateSessionRequest(BaseModel):
    title: str | None = None
    all_documents: bool = True
    selected_document_ids: list[str] = Field(default_factory=list)


class PatchSessionRequest(BaseModel):
    title: str | None = None
    all_documents: bool | None = None
    selected_document_ids: list[str] | None = None


class DeleteSessionResponse(BaseModel):
    session_id: str
    deleted: bool
    already_absent: bool = False
    request_id: str = ""


def grounding_status_for(validation_status: str) -> GroundingStatusName:
    mapping: dict[str, GroundingStatusName] = {
        "valid": "grounded",
        "insufficient_evidence": "insufficient_evidence",
        "missing_citations": "unverified",
        "invalid_citation": "invalid_citation",
        "malformed_output": "malformed_output",
    }
    return mapping.get(validation_status, "malformed_output")
