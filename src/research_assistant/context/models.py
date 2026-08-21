"""Citation-aware context types. Runtime only; not persisted."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CitationSource:
    citation_id: str
    chunk_id: str
    document_id: str
    filename: str
    page_start: int | None
    page_end: int | None
    section_path: tuple[str, ...]
    content_hash: str
    chunker_id: str

    def compact_locator(self) -> str:
        """Human locator from stored provenance. Never invents pages or sections."""
        name = self.filename.strip() or self.document_id
        parts = [name]
        if self.page_start is not None:
            if self.page_end is not None and self.page_end != self.page_start:
                parts.append(f"pp. {self.page_start}–{self.page_end}")
            else:
                parts.append(f"p. {self.page_start}")
        if self.section_path:
            parts.append('section "' + " > ".join(self.section_path) + '"')
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "filename": self.filename,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "section_path": list(self.section_path),
            "content_hash": self.content_hash,
            "chunker_id": self.chunker_id,
            "locator": self.compact_locator(),
        }


@dataclass(frozen=True)
class ContextItem:
    citation_id: str
    text: str
    truncated: bool
    rank: int
    rerank_score: float | None
    retrieval_rank: int
    source: CitationSource

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "text": self.text,
            "truncated": self.truncated,
            "rank": self.rank,
            "rerank_score": self.rerank_score,
            "retrieval_rank": self.retrieval_rank,
            "source": self.source.to_dict(),
        }


@dataclass(frozen=True)
class ContextSelectionDecision:
    """Per-candidate context decision for developer tracing."""

    chunk_id: str
    selected: bool
    context_position: int | None
    reason: str | None
    tokens_used_before: int
    candidate_tokens: int | None
    tokens_added: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "selected": self.selected,
            "context_position": self.context_position,
            "reason": self.reason,
            "tokens_used_before": self.tokens_used_before,
            "candidate_tokens": self.candidate_tokens,
            "tokens_added": self.tokens_added,
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class ContextDiagnostics:
    input_count: int
    selected_count: int
    skipped_count: int
    duplicate_count: int
    redundant_count: int
    truncated_count: int
    skipped_budget_count: int
    max_context_tokens: int
    estimated_tokens: int
    accounting: str
    citation_ids: tuple[str, ...]
    source_document_count: int
    skipped_chunk_ids: tuple[str, ...]
    selection_decisions: tuple[ContextSelectionDecision, ...] = ()
    context_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_count": self.input_count,
            "selected_count": self.selected_count,
            "skipped_count": self.skipped_count,
            "duplicate_count": self.duplicate_count,
            "redundant_count": self.redundant_count,
            "truncated_count": self.truncated_count,
            "skipped_budget_count": self.skipped_budget_count,
            "max_context_tokens": self.max_context_tokens,
            "estimated_tokens": self.estimated_tokens,
            "accounting": self.accounting,
            "citation_ids": list(self.citation_ids),
            "source_document_count": self.source_document_count,
            "skipped_chunk_ids": list(self.skipped_chunk_ids),
            "selection_decisions": [
                item.to_dict() for item in self.selection_decisions
            ],
            "context_ms": round(self.context_ms, 2),
        }


@dataclass(frozen=True)
class ContextBundle:
    query: str
    items: tuple[ContextItem, ...]
    rendered_text: str
    diagnostics: ContextDiagnostics

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "items": [item.to_dict() for item in self.items],
            "rendered_text": self.rendered_text,
            "diagnostics": self.diagnostics.to_dict(),
        }
