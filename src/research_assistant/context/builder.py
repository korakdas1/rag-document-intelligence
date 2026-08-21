"""Citation-aware context construction. Does not retrieve, rerank, or call an LLM."""

from __future__ import annotations

import time
from collections.abc import Sequence

from research_assistant.core.errors import ContextError
from research_assistant.core.logging import get_logger
from research_assistant.core.settings import Settings, load_settings
from research_assistant.context.format import (
    ACCOUNTING,
    estimated_tokens,
    render_bundle,
    render_evidence_block,
)
from research_assistant.context.models import (
    CitationSource,
    ContextBundle,
    ContextDiagnostics,
    ContextItem,
    ContextSelectionDecision,
)
from research_assistant.retrieval.models import RetrievalHit

logger = get_logger("research_assistant.context")

_MIN_EVIDENCE_CHARS = 16


class CitationAwareContextBuilder:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or load_settings()

    def build(
        self,
        hits: Sequence[RetrievalHit],
        *,
        query: str = "",
        max_tokens: int | None = None,
    ) -> ContextBundle:
        budget = max_tokens if max_tokens is not None else self._settings.max_context_tokens
        if budget < 1:
            raise ContextError("max_context_tokens must be >= 1", code="invalid_budget")

        started = time.perf_counter()
        selected: list[ContextItem] = []
        blocks: list[str] = []
        seen_chunk_ids: set[str] = set()
        seen_hashes: set[tuple[str, str]] = set()
        skipped_ids: list[str] = []
        decisions: list[ContextSelectionDecision] = []
        duplicate_count = 0
        redundant_count = 0
        truncated_count = 0
        skipped_budget_count = 0
        used_tokens = 0

        for index, hit in enumerate(hits):
            if hit.chunk_id in seen_chunk_ids:
                duplicate_count += 1
                skipped_ids.append(hit.chunk_id)
                decisions.append(
                    ContextSelectionDecision(
                        chunk_id=hit.chunk_id,
                        selected=False,
                        context_position=None,
                        reason="duplicate_chunk",
                        tokens_used_before=used_tokens,
                        candidate_tokens=None,
                        tokens_added=0,
                        truncated=False,
                    )
                )
                continue
            hash_key = (hit.document_id, hit.content_hash)
            if hit.content_hash and hash_key in seen_hashes:
                redundant_count += 1
                skipped_ids.append(hit.chunk_id)
                decisions.append(
                    ContextSelectionDecision(
                        chunk_id=hit.chunk_id,
                        selected=False,
                        context_position=None,
                        reason="redundant_content",
                        tokens_used_before=used_tokens,
                        candidate_tokens=None,
                        tokens_added=0,
                        truncated=False,
                    )
                )
                continue

            citation_id = f"S{len(selected) + 1}"
            prefix_len = 2 if blocks else 0  # "\n\n" between items
            remaining = budget - used_tokens
            candidate_tokens = _full_item_cost(citation_id, hit, prefix_len)
            fitted = _fit_item(citation_id, hit, remaining, prefix_len)
            if fitted is None:
                skipped_budget_count += 1
                skipped_ids.append(hit.chunk_id)
                decisions.append(
                    ContextSelectionDecision(
                        chunk_id=hit.chunk_id,
                        selected=False,
                        context_position=None,
                        reason="context_budget",
                        tokens_used_before=used_tokens,
                        candidate_tokens=candidate_tokens,
                        tokens_added=0,
                        truncated=False,
                    )
                )
                for later in hits[index + 1 :]:
                    skipped_budget_count += 1
                    skipped_ids.append(later.chunk_id)
                    decisions.append(
                        ContextSelectionDecision(
                            chunk_id=later.chunk_id,
                            selected=False,
                            context_position=None,
                            reason="after_context_budget_cutoff",
                            tokens_used_before=used_tokens,
                            candidate_tokens=None,
                            tokens_added=0,
                            truncated=False,
                        )
                    )
                break

            block, excerpt, truncated, cost = fitted
            if truncated:
                truncated_count += 1
            source = CitationSource(
                citation_id=citation_id,
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                filename=hit.filename,
                page_start=hit.page_start,
                page_end=hit.page_end,
                section_path=hit.section_path,
                content_hash=hit.content_hash,
                chunker_id=hit.chunker_id,
            )
            selected.append(
                ContextItem(
                    citation_id=citation_id,
                    text=excerpt,
                    truncated=truncated,
                    rank=len(selected) + 1,
                    rerank_score=hit.rerank_score,
                    retrieval_rank=hit.rank,
                    source=source,
                )
            )
            blocks.append(block)
            decisions.append(
                ContextSelectionDecision(
                    chunk_id=hit.chunk_id,
                    selected=True,
                    context_position=len(selected),
                    reason=None,
                    tokens_used_before=used_tokens,
                    candidate_tokens=candidate_tokens,
                    tokens_added=cost,
                    truncated=truncated,
                )
            )
            used_tokens += cost
            seen_chunk_ids.add(hit.chunk_id)
            if hit.content_hash:
                seen_hashes.add(hash_key)

        rendered = render_bundle(blocks)
        estimated = estimated_tokens(rendered)
        documents = {item.source.document_id for item in selected}
        diagnostics = ContextDiagnostics(
            input_count=len(hits),
            selected_count=len(selected),
            skipped_count=len(skipped_ids),
            duplicate_count=duplicate_count,
            redundant_count=redundant_count,
            truncated_count=truncated_count,
            skipped_budget_count=skipped_budget_count,
            max_context_tokens=budget,
            estimated_tokens=estimated,
            accounting=ACCOUNTING,
            citation_ids=tuple(item.citation_id for item in selected),
            source_document_count=len(documents),
            skipped_chunk_ids=tuple(skipped_ids),
            selection_decisions=tuple(decisions),
            context_ms=(time.perf_counter() - started) * 1000,
        )
        if estimated > budget:
            raise ContextError(
                "Constructed context exceeded the declared token budget",
                code="budget_exceeded",
            )
        logger.info(
            "context_built selected=%s skipped=%s tokens=%s/%s",
            diagnostics.selected_count,
            diagnostics.skipped_count,
            diagnostics.estimated_tokens,
            budget,
        )
        return ContextBundle(
            query=query,
            items=tuple(selected),
            rendered_text=rendered,
            diagnostics=diagnostics,
        )


def _fit_item(
    citation_id: str,
    hit: RetrievalHit,
    remaining: int,
    prefix_len: int,
) -> tuple[str, str, bool, int] | None:
    full_block = render_evidence_block(citation_id, hit, hit.text)
    full_cost = estimated_tokens(("x" * prefix_len) + full_block if prefix_len else full_block)
    if full_cost <= remaining:
        return full_block, hit.text, False, full_cost

    header = render_evidence_block(citation_id, hit, "")
    header_cost = estimated_tokens(("x" * prefix_len) + header if prefix_len else header)
    if header_cost + estimated_tokens("x" * _MIN_EVIDENCE_CHARS) > remaining:
        return None

    low = _MIN_EVIDENCE_CHARS
    high = len(hit.text)
    best: tuple[str, str, int] | None = None
    while low <= high:
        mid = (low + high) // 2
        excerpt = hit.text[:mid]
        block = render_evidence_block(citation_id, hit, excerpt)
        cost = estimated_tokens(("x" * prefix_len) + block if prefix_len else block)
        if cost <= remaining:
            best = (block, excerpt, cost)
            low = mid + 1
        else:
            high = mid - 1
    if best is None:
        return None
    block, excerpt, cost = best
    return block, excerpt, excerpt != hit.text, cost


def _full_item_cost(citation_id: str, hit: RetrievalHit, prefix_len: int) -> int:
    block = render_evidence_block(citation_id, hit, hit.text)
    rendered = ("x" * prefix_len) + block if prefix_len else block
    return estimated_tokens(rendered)
