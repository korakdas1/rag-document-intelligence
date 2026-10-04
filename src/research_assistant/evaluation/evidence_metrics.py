"""Passage presence in exact context excerpts, with source provenance."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from research_assistant.context.models import ContextBundle
from research_assistant.evaluation.models import EvaluationExample, GoldPassage

FULL_GOLD_PASSAGE_COVERAGE = "FULL_GOLD_PASSAGE_COVERAGE"
PARTIAL_GOLD_PASSAGE_COVERAGE = "PARTIAL_GOLD_PASSAGE_COVERAGE"
NO_GOLD_PASSAGE_COVERAGE = "NO_GOLD_PASSAGE_COVERAGE"
NOT_APPLICABLE = "NOT_APPLICABLE"


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def context_blocks(bundle: ContextBundle) -> list[dict[str, Any]]:
    return [
        {
            "citation_id": item.citation_id, "chunk_id": item.source.chunk_id,
            "document_id": item.source.document_id, "filename": item.source.filename,
            "text": item.text, "truncated": item.truncated,
        }
        for item in bundle.items
    ]


def passage_hits(passages: Sequence[GoldPassage], blocks: Sequence[dict[str, Any]]) -> list[bool]:
    """A whole normalized label must occur inside one excerpt from its filename.

    Do not concatenate excerpts: that could invent a passage across a missing gap.
    """
    return [
        bool(normalize(passage.text)) and any(
            block.get("filename") == passage.filename
            and normalize(passage.text) in normalize(str(block.get("text") or ""))
            for block in blocks
        )
        for passage in passages
    ]


def passage_metrics(
    example: EvaluationExample, blocks: Sequence[dict[str, Any]], *, prefix: str = "rendered_gold",
) -> dict[str, Any]:
    hits = passage_hits(example.gold_passages, blocks) if example.answerable else []
    return {
        f"{prefix}_passage_hits": hits,
        f"{prefix}_any": any(hits) if hits else None,
        f"{prefix}_all": all(hits) if hits else None,
        f"{prefix}_passage_recall": sum(hits) / len(hits) if hits else None,
    }


def classify_cited_gold_coverage(recall: float | None) -> str:
    """Coverage of labeled gold in cited excerpts, never answer entailment."""
    if recall is None:
        return NOT_APPLICABLE
    if recall == 1.0:
        return FULL_GOLD_PASSAGE_COVERAGE
    if recall > 0:
        return PARTIAL_GOLD_PASSAGE_COVERAGE
    return NO_GOLD_PASSAGE_COVERAGE
