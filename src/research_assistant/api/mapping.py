"""Thin domain → API DTO mapping. Does not retrieve or generate."""

from __future__ import annotations

from pathlib import Path

from research_assistant.api.schemas import (
    AskResponse,
    CandidateView,
    CitationView,
    DiagnosticsView,
    DocumentStatusName,
    DocumentSummary,
    SourceView,
    grounding_status_for,
)
from research_assistant.core.resource import sanitize_public_error
from research_assistant.core.types import IndexStatus, ParseStatus
from research_assistant.generation.rag import RAGResult
from research_assistant.storage.records import DocumentRecord


def document_status(
    record: DocumentRecord, *, chunk_count: int, indexed: bool
) -> DocumentStatusName:
    if record.parse_status is ParseStatus.FAILED:
        return "failed"
    if chunk_count <= 0:
        return "parsed"
    if not indexed:
        return "chunked"
    return "ready"


def source_available(record: DocumentRecord) -> bool:
    path = Path(record.source_path)
    try:
        return path.is_file()
    except OSError:
        return False


def checksum_prefix(checksum: str, length: int = 12) -> str:
    return checksum[:length] if checksum else ""


def to_document_summary(
    record: DocumentRecord,
    *,
    chunk_count: int,
    indexed: bool,
) -> DocumentSummary:
    return DocumentSummary(
        document_id=record.document_id,
        filename=record.filename,
        content_type=record.content_type.value,
        status=document_status(record, chunk_count=chunk_count, indexed=indexed),
        page_count=record.page_count,
        chunk_count=chunk_count,
        byte_size=record.byte_size,
        warning_count=record.warning_count,
        ingested_at=record.ingested_at,
        updated_at=record.updated_at,
        parse_status=record.parse_status.value,
        error_message=(
            sanitize_public_error(record.error_message, filename=record.filename)
            if record.error_message
            else None
        ),
        source_available=source_available(record),
        checksum_prefix=checksum_prefix(record.checksum_sha256),
    )


def index_is_ready(status: IndexStatus | None) -> bool:
    return status is IndexStatus.READY


def to_ask_response(result: RAGResult, *, request_id: str = "") -> AskResponse:
    answer = result.answer
    cited_ids = {item.citation_id for item in answer.citations}
    sources = [
        SourceView(
            citation_id=item.citation_id,
            filename=item.source.filename,
            document_id=item.source.document_id,
            page_start=item.source.page_start,
            page_end=item.source.page_end,
            section_path=list(item.source.section_path),
            locator=item.source.compact_locator(),
            text=item.text,
            truncated=item.truncated,
            cited_by_model=item.citation_id in cited_ids,
        )
        for item in result.evidence.context.items
    ]
    citations = [
        CitationView(
            citation_id=item.citation_id,
            filename=item.source.filename,
            document_id=item.source.document_id,
            page_start=item.source.page_start,
            page_end=item.source.page_end,
            section_path=list(item.source.section_path),
            locator=item.source.compact_locator(),
            occurrence_count=item.occurrence_count,
        )
        for item in answer.citations
    ]
    search = result.evidence.search.diagnostics
    rerank = result.evidence.rerank.diagnostics
    gen = answer.diagnostics
    resolution = result.resolution
    context_positions = {
        item.source.chunk_id: item.rank
        for item in result.evidence.context.items
    }
    candidates = [
        CandidateView(
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            filename=hit.filename,
            rank=hit.rank,
            page_start=hit.page_start,
            page_end=hit.page_end,
            section_path=list(hit.section_path),
            dense_rank=hit.dense_rank,
            lexical_rank=hit.lexical_rank,
            rerank_rank=hit.rerank_rank,
            retrievers=list(hit.retrievers or ((hit.retriever,) if hit.retriever else ())),
            rerank_score=hit.rerank_score,
            selected_in_context=hit.chunk_id in context_positions,
            context_position=context_positions.get(hit.chunk_id),
        )
        for hit in result.evidence.rerank.hits[:12]
    ]
    return AskResponse(
        question=result.original_query or result.query,
        answer=answer.answer_text,
        grounding_status=grounding_status_for(answer.validation_status.value),
        validation_status=answer.validation_status.value,
        insufficient_evidence=answer.insufficient_evidence,
        citations=citations,
        sources=sources,
        diagnostics=DiagnosticsView(
            retrieval_mode=search.mode,
            rerank_enabled=rerank.enabled,
            candidate_count=rerank.input_count,
            context_source_count=len(result.evidence.context.items),
            dense_ms=search.dense_ms,
            lexical_ms=search.lexical_ms,
            fusion_ms=search.fusion_ms,
            retrieval_ms=search.total_ms,
            rerank_ms=rerank.inference_ms,
            generation_ms=gen.generation_ms,
            first_pass_generation_ms=gen.first_pass_generation_ms,
            repair_ms=gen.repair_ms,
            llm_id=gen.llm_id,
            reranker_id=rerank.reranker_id,
            validation_status=answer.validation_status.value,
            candidates=candidates,
            original_question=resolution.original_question if resolution else result.original_query,
            retrieval_query=resolution.retrieval_query if resolution else result.query,
            rewrite_applied=bool(resolution and resolution.rewrite_applied),
            followup_detected=bool(resolution and resolution.followup_detected),
            ambiguous_followup=bool(resolution and resolution.ambiguous),
            history_turns_used=resolution.diagnostics.history_turns_used if resolution else 0,
            resolver_id=resolution.diagnostics.resolver_id if resolution else None,
            resolver_method=resolution.diagnostics.method if resolution else None,
            resolver_ms=resolution.diagnostics.elapsed_ms if resolution else None,
            conversation_subjects=list(resolution.diagnostics.entities) if resolution else [],
            repair_attempts=gen.repair_attempts,
            generation_question=result.query,
            context_citation_ids=[
                item.citation_id for item in result.evidence.context.items
            ],
            insufficient_evidence=answer.insufficient_evidence,
            parsed_inline_citation_ids=list(gen.parsed_inline_citation_ids),
            validated_citation_ids=list(gen.validated_citation_ids),
            structured_citation_ids=list(gen.structured_citation_ids),
            prompt_version=gen.prompt_version or None,
            parser_version=gen.parser_version or None,
            generation_protocol_status=gen.generation_protocol_status or None,
            parser_mode=gen.parser_mode or None,
            normalization_applied=list(gen.normalization_applied),
            raw_output_category=gen.raw_output_category or None,
            format_repair_attempted=gen.format_repair_attempted,
            format_repair_succeeded=gen.format_repair_succeeded,
        ),
        request_id=request_id,
    )
