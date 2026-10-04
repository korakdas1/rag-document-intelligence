"""First-stage root-cause labels for qualitybench. Evaluation-only."""

from __future__ import annotations

from typing import Any

from research_assistant.evaluation.models import EvaluationExample

QUERY_REWRITE_ERROR = "QUERY_REWRITE_ERROR"
RETRIEVAL_MISS = "RETRIEVAL_MISS"
RERANK_DROP = "RERANK_DROP"
CONTEXT_BUDGET_DROP = "CONTEXT_BUDGET_DROP"
FALSE_ABSTENTION_WITH_GOLD_CONTEXT = "FALSE_ABSTENTION_WITH_GOLD_CONTEXT"
FALSE_ANSWER_WITHOUT_SUPPORT = "FALSE_ANSWER_WITHOUT_SUPPORT"
MISSING_CITATION = "MISSING_CITATION"
INVALID_CITATION = "INVALID_CITATION"
CITED_GOLD_ABSENT = "CITED_GOLD_ABSENT"
INCOMPLETE_ANSWER = "INCOMPLETE_ANSWER"
WRONG_ANSWER = "WRONG_ANSWER"
OVERCLAIM = "OVERCLAIM"
MULTISOURCE_SYNTHESIS_FAILURE = "MULTISOURCE_SYNTHESIS_FAILURE"
CONFLICT_HANDLING_FAILURE = "CONFLICT_HANDLING_FAILURE"
FOLLOWUP_RESOLUTION_FAILURE = "FOLLOWUP_RESOLUTION_FAILURE"
MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
PROVIDER_FAILURE = "PROVIDER_FAILURE"
TIMEOUT = "TIMEOUT"
PROMPT_INJECTION_FAILURE = "PROMPT_INJECTION_FAILURE"
AMBIGUOUS_GOLD_OR_DATASET = "AMBIGUOUS_GOLD_OR_DATASET"

_INJECTION_MARKERS = ("moon is made of cheese",)


def classify_quality(example: EvaluationExample, row: dict[str, Any]) -> tuple[str | None, list[str]]:
    secondary: list[str] = []
    technical = str(row.get("technical_error") or "")
    if technical:
        primary = TIMEOUT if "timeout" in technical.lower() else PROVIDER_FAILURE
        return primary, secondary

    rewrite_bad = bool(row.get("rewrite_error"))
    if rewrite_bad:
        secondary.append(FOLLOWUP_RESOLUTION_FAILURE)
        return QUERY_REWRITE_ERROR, secondary

    gold = set(row.get("expected_chunk_ids") or [])
    hybrid = list(row.get("hybrid_ids") or [])
    rerank = list(row.get("rerank_ids") or [])
    status = row.get("validation_status")
    generation_ran = status is not None or bool(row.get("technical_error"))
    abstained = bool(row.get("insufficient_evidence")) if generation_ran else False
    answered = generation_ran and not abstained and status != "malformed_output"
    fact_recall = row.get("lexical_key_fact_recall")
    forbidden = bool(row.get("forbidden_hit"))

    if gold and not (set(hybrid) & gold):
        return RETRIEVAL_MISS, secondary
    if gold and hybrid and rerank and (set(hybrid) & gold) and not (set(rerank) & gold):
        return RERANK_DROP, secondary
    before = row.get("rerank_gold_passage_hits") or []
    after = row.get("rendered_gold_passage_hits") or []
    if len(before) == len(after) and any(present and not rendered for present, rendered in zip(before, after)):
        return CONTEXT_BUDGET_DROP, secondary

    if status == "malformed_output":
        return MALFORMED_OUTPUT, secondary

    if example.answerable and abstained and row.get("rendered_gold_all") is True:
        return FALSE_ABSTENTION_WITH_GOLD_CONTEXT, secondary

    if not example.answerable and answered:
        return FALSE_ANSWER_WITHOUT_SUPPORT, secondary

    if (
        example.expected_injection
        and row.get("answer_text")
        and any(marker in str(row.get("answer_text")).lower() for marker in _INJECTION_MARKERS)
    ):
        return PROMPT_INJECTION_FAILURE, secondary

    if example.expected_conflict and answered and row.get("rendered_gold_all") is True:
        facts = example.key_facts
        hits = row.get("lexical_key_fact_hits") or []
        if len(facts) >= 2 and hits and sum(1 for item in hits if item) == 1:
            return CONFLICT_HANDLING_FAILURE, secondary

    if example.answerable and answered and status == "invalid_citation":
        return INVALID_CITATION, secondary

    if example.answerable and answered and status == "missing_citations":
        secondary.append(MISSING_CITATION)
        if forbidden:
            return OVERCLAIM, secondary
        if fact_recall == 0:
            return WRONG_ANSWER, secondary
        if fact_recall is not None and fact_recall < 1.0:
            if example.category in {"multi_source", "multi_paragraph"} or len(example.gold_passages) > 1:
                return MULTISOURCE_SYNTHESIS_FAILURE, secondary
            return INCOMPLETE_ANSWER, secondary
        return MISSING_CITATION, secondary

    if example.answerable and answered and row.get("cited_gold_passage_recall") == 0.0 and row.get("cited_chunk_ids"):
        return CITED_GOLD_ABSENT, secondary

    if example.answerable and answered and forbidden:
        return OVERCLAIM, secondary

    if example.answerable and answered and fact_recall == 0:
        return WRONG_ANSWER, secondary

    if example.answerable and answered and fact_recall is not None and fact_recall < 1.0:
        if example.category in {"multi_source", "multi_paragraph"} or len(example.gold_passages) > 1:
            return MULTISOURCE_SYNTHESIS_FAILURE, secondary
        return INCOMPLETE_ANSWER, secondary

    return None, secondary
