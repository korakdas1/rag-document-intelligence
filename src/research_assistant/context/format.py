"""Format evidence blocks. Provenance comes only from the hit; nothing is invented."""

from __future__ import annotations

from research_assistant.chunking.identity import approx_token_count
from research_assistant.retrieval.models import RetrievalHit

ACCOUNTING = "approx_char/4"
ITEM_SEPARATOR = "\n\n"


def estimated_tokens(text: str) -> int:
    return approx_token_count(len(text))


def render_evidence_block(
    citation_id: str,
    hit: RetrievalHit,
    evidence_text: str,
) -> str:
    lines = [f"[{citation_id}]"]
    lines.extend(source_header_lines(hit))
    lines.append("Evidence:")
    lines.append(evidence_text)
    return "\n".join(lines)


def source_header_lines(hit: RetrievalHit) -> list[str]:
    filename = hit.filename.strip()
    source = filename if filename else hit.document_id
    lines = [f"Source: {source}"]
    if hit.page_start is not None:
        if hit.page_end is not None and hit.page_end != hit.page_start:
            lines.append(f"Pages: {hit.page_start}–{hit.page_end}")
        else:
            lines.append(f"Pages: {hit.page_start}")
    if hit.section_path:
        lines.append("Section: " + " > ".join(hit.section_path))
    return lines


def render_bundle(blocks: list[str]) -> str:
    return ITEM_SEPARATOR.join(blocks)
