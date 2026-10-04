"""Qualitybench metrics. Deterministic; not LLM-as-judge."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from research_assistant.evaluation.latency import summarize_latency
from research_assistant.evaluation.metrics import abstention_counts, mean, rate, token_f1
from research_assistant.evaluation.models import EvaluationExample, GoldPassage
from research_assistant.evaluation.evidence_metrics import passage_hits

PRODUCT_GROUNDED = "GROUNDED"
PRODUCT_UNVERIFIED = "UNVERIFIED"
PRODUCT_NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"
PRODUCT_FORMAT_ERROR = "FORMAT_ERROR"
PRODUCT_TECHNICAL_ERROR = "TECHNICAL_ERROR"
PRODUCT_INVALID_CITATION = "INVALID_CITATION"


def normalize_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def key_fact_hits(answer: str, facts: Sequence[str]) -> list[bool]:
    body = normalize_text(answer)
    return [normalize_text(fact) in body for fact in facts if fact.strip()]


def key_fact_recall(answer: str, facts: Sequence[str]) -> float | None:
    facts = [item for item in facts if str(item).strip()]
    if not facts:
        return None
    hits = key_fact_hits(answer, facts)
    return sum(1 for item in hits if item) / len(hits)


def forbidden_hit(answer: str, forbidden: Sequence[str]) -> bool:
    body = normalize_text(answer)
    return any(normalize_text(item) in body for item in forbidden if item.strip())


_CONFLICT_MARKERS = (
    "conflict",
    "disagree",
    "contradict",
    "incompatible",
    "do not agree",
    "does not agree",
    "don't agree",
    "sources conflict",
    "while another",
    "another document",
    "another source",
    "one document gives",
    "other document",
)


def conflict_reported(answer: str) -> bool:
    """Generic disagreement language. Does not use corpus-specific dates or names."""
    body = normalize_text(answer)
    return any(marker in body for marker in _CONFLICT_MARKERS)


def slot_results(
    answer: str, example: EvaluationExample, cited_blocks: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Substring label matches and provenance-aware cited excerpt overlap only."""
    body = normalize_text(answer)
    return [
        {
            "claim_id": claim.claim_id,
            "lexical_answer_match": bool(claim.text) and normalize_text(claim.text) in body,
            "cited_gold_overlap": passage_hits(
                [GoldPassage(claim.filename, claim.gold_text)], cited_blocks,
            )[0] if claim.filename and claim.gold_text else None,
        }
        for claim in example.claims
    ]


def product_status(validation_status: str | None, *, technical: bool = False) -> str:
    if technical:
        return PRODUCT_TECHNICAL_ERROR
    mapping = {
        "valid": PRODUCT_GROUNDED,
        "missing_citations": PRODUCT_UNVERIFIED,
        "insufficient_evidence": PRODUCT_NOT_ENOUGH_EVIDENCE,
        "invalid_citation": PRODUCT_INVALID_CITATION,
        "malformed_output": PRODUCT_FORMAT_ERROR,
    }
    return mapping.get(validation_status or "", PRODUCT_FORMAT_ERROR)


def unverified_reason(
    *,
    validation_status: str | None,
    key_fact_recall_value: float | None,
) -> str | None:
    if validation_status != "missing_citations":
        if validation_status == "invalid_citation":
            return "invalid_citation"
        if validation_status == "malformed_output":
            return "malformed_marker"
        return None
    if key_fact_recall_value is None:
        return "other_validation_failure"
    if key_fact_recall_value >= 0.5:
        return "useful_missing_citation"
    if key_fact_recall_value > 0:
        return "partial_missing_citation"
    return "wrong_missing_citation"


def first_gold_rank(retrieved_ids: Sequence[str], gold_ids: set[str]) -> int | None:
    if not gold_ids:
        return None
    for index, item in enumerate(retrieved_ids, start=1):
        if item in gold_ids:
            return index
    return None


def gold_present(retrieved_ids: Sequence[str], gold_ids: set[str], *, k: int | None = None) -> bool | None:
    if not gold_ids:
        return None
    pool = list(retrieved_ids) if k is None else list(retrieved_ids)[:k]
    return bool(gold_ids & set(pool))


def quality_aggregates(
    rows: Sequence[dict[str, Any]],
    examples: Sequence[EvaluationExample],
) -> dict[str, Any]:
    by_id = {item.example_id: item for item in examples}
    n = len(rows)
    answerable_rows = [row for row in rows if by_id[row["example_id"]].answerable]
    unanswerable_rows = [row for row in rows if not by_id[row["example_id"]].answerable]
    status_all = Counter(row.get("product_status") for row in rows)
    status_ans = Counter(row.get("product_status") for row in answerable_rows)
    status_unans = Counter(row.get("product_status") for row in unanswerable_rows)
    expected = []
    predicted = []
    for row in rows:
        if row.get("validation_status") is None and not row.get("technical_error"):
            continue
        expected.append(by_id[row["example_id"]].expected_insufficient)
        predicted.append(bool(row.get("insufficient_evidence")))
    tp = fp = fn = tn = 0
    if expected:
        tp, fp, fn, tn = abstention_counts(expected, predicted)
    primary = Counter(row.get("primary_failure") for row in rows if row.get("primary_failure"))
    unverified = Counter(row.get("unverified_reason") for row in rows if row.get("unverified_reason"))
    gold_ctx = [
        1.0 if row.get("gold_chunk_selected") else 0.0
        for row in answerable_rows
        if row.get("gold_chunk_selected") is not None
    ]
    gold_hybrid = [
        1.0 if row.get("gold_in_hybrid") else 0.0
        for row in answerable_rows
        if row.get("gold_in_hybrid") is not None
    ]
    gold_rerank = [
        1.0 if row.get("gold_in_rerank") else 0.0
        for row in answerable_rows
        if row.get("gold_in_rerank") is not None
    ]
    fact_recalls = [row.get("lexical_key_fact_recall") for row in answerable_rows]
    cited = [
        row
        for row in answerable_rows
        if row.get("validation_status")
        and not row.get("insufficient_evidence")
        and row.get("validation_status") not in {"malformed_output"}
    ]
    covered = [row for row in cited if row.get("cited_chunk_ids")]
    missing = sum(1 for row in rows if row.get("validation_status") == "missing_citations")
    invalid = sum(1 for row in rows if row.get("validation_status") == "invalid_citation")
    malformed = sum(1 for row in rows if row.get("validation_status") == "malformed_output")
    support_scores = [row.get("cited_gold_passage_recall") for row in rows]
    grounded = [row for row in rows if row.get("product_status") == PRODUCT_GROUNDED]
    grounded_full_gold = sum(1 for row in grounded if row.get("product_grounded_with_full_cited_gold"))
    grounded_no_gold = sum(1 for row in grounded if row.get("product_grounded_without_cited_gold"))
    conflict_rows = [row for row in rows if by_id[row["example_id"]].expected_conflict]
    non_conflict_answered = [
        row
        for row in rows
        if not by_id[row["example_id"]].expected_conflict
        and not row.get("insufficient_evidence")
        and row.get("validation_status") not in {None, "malformed_output"}
    ]
    slot_complete = 0
    slot_total = 0
    slot_n = 0
    slot_answered = 0
    slot_cited = 0
    for row in rows:
        slots = row.get("claim_slots") or []
        if not slots:
            continue
        slot_total += 1
        if slots and all(item.get("lexical_answer_match") for item in slots):
            slot_complete += 1
        for item in slots:
            slot_n += 1
            if item.get("lexical_answer_match"):
                slot_answered += 1
            if item.get("cited_gold_overlap"):
                slot_cited += 1
    phrase_groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        group = by_id[row["example_id"]].paraphrase_group
        if group:
            phrase_groups.setdefault(group, []).append(row)
    stable_groups = 0
    for items in phrase_groups.values():
        statuses = {item.get("product_status") for item in items}
        facts = {item.get("lexical_key_fact_recall") for item in items}
        if len(statuses) == 1 and len(facts) == 1:
            stable_groups += 1
    phrase_stats = {
        "groups": len(phrase_groups),
        "stable_groups": stable_groups,
        "consistency_rate": rate(stable_groups, len(phrase_groups)),
    }
    repair_runs = [row for row in rows if (row.get("repair_attempts") or 0) > 0]
    support_counts = Counter(row.get("cited_gold_coverage_class") for row in grounded if row.get("cited_gold_coverage_class"))
    drift_kinds: Counter[str] = Counter()
    false_grounding_repair = 0
    for row in rows:
        drift = row.get("repair_drift") or {}
        for kind in drift.get("kinds") or []:
            drift_kinds[str(kind)] += 1
        if (
            row.get("repair_attempts")
            and row.get("product_status") == PRODUCT_GROUNDED
            and row.get("cited_gold_coverage_class") == "NO_GOLD_PASSAGE_COVERAGE"
            and (row.get("first_pass_validation_status") == "missing_citations")
        ):
            false_grounding_repair += 1
    call_counts = [row.get("llm_calls") for row in rows if row.get("llm_calls") is not None]
    guessed_referent = sum(
        1
        for row in rows
        if not by_id[row["example_id"]].history
        and row.get("resolver_method") == "unresolved_no_history"
        and not row.get("insufficient_evidence")
        and row.get("validation_status") not in {None, "malformed_output"}
    )
    f1_scores = [
        token_f1(str(row.get("answer_text") or ""), by_id[row["example_id"]].reference_answer or "")
        for row in rows
    ]
    false_abs_with_ctx = sum(
        1
        for row in answerable_rows
        if row.get("insufficient_evidence") and row.get("rendered_gold_all") is True
    )
    latencies: dict[str, list[float]] = {
        "retrieval_ms": [],
        "rerank_ms": [],
        "generation_ms": [],
        "first_pass_generation_ms": [],
        "repair_ms": [],
        "total_ms": [],
    }
    for row in rows:
        timings = row.get("timings_ms") or {}
        for key in latencies:
            if key in timings:
                latencies[key].append(float(timings[key]))
    return {
        "n": n,
        "n_answerable": len(answerable_rows),
        "n_unanswerable": len(unanswerable_rows),
        "product_status": dict(status_all),
        "product_status_answerable": dict(status_ans),
        "product_status_unanswerable": dict(status_unans),
        "abstention": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "precision": rate(tp, tp + fp),
            "recall": rate(tp, tp + fn),
            "false_answer_rate": rate(fn, tp + fn),
            "false_abstention_rate": rate(fp, fp + tn),
            "false_abstention_with_gold_context": false_abs_with_ctx,
        },
        "retrieval_to_context": {
            "gold_in_hybrid_rate": mean(gold_hybrid),
            "gold_in_rerank_rate": mean(gold_rerank),
            "gold_chunk_selected_rate": mean(gold_ctx),
            "context_gold_chunk_recall": mean([row.get("context_gold_chunk_recall") for row in answerable_rows]),
            "rendered_gold_any_rate": mean([float(row["rendered_gold_any"]) for row in answerable_rows if row.get("rendered_gold_any") is not None]),
            "rendered_gold_all_rate": mean([float(row["rendered_gold_all"]) for row in answerable_rows if row.get("rendered_gold_all") is not None]),
            "rendered_gold_passage_recall": mean([row.get("rendered_gold_passage_recall") for row in answerable_rows]),
        },
        "answer_content": {
            "lexical_key_fact_recall": mean(fact_recalls),
            "all_lexical_key_facts_matched": rate(
                sum(1 for item in fact_recalls if item == 1.0),
                sum(1 for item in fact_recalls if item is not None),
            ),
            "reference_token_f1_diagnostic": mean(f1_scores),
        },
        "citations": {
            "answers_requiring_citation": len(cited),
            "answers_with_valid_citation": len(covered),
            "citation_coverage": rate(len(covered), len(cited)),
            "missing_citation_count": missing,
            "invalid_citation_count": invalid,
            "malformed_count": malformed,
            "cited_gold_passage_recall": mean(support_scores),
            "product_grounded": len(grounded),
            "product_grounded_with_full_cited_gold": grounded_full_gold,
            "product_grounded_without_cited_gold": grounded_no_gold,
        },
        "conflict": {
            "n_expected_conflict": len(conflict_rows),
            "true_conflict_reported": sum(1 for row in conflict_rows if row.get("conflict_reported")),
            "true_conflict_both_key_facts": sum(
                1
                for row in conflict_rows
                if row.get("lexical_key_fact_recall") == 1.0
            ),
            "collapsed": sum(
                1
                for row in conflict_rows
                if not row.get("insufficient_evidence")
                and not row.get("conflict_reported")
                and row.get("validation_status") not in {None, "malformed_output"}
            ),
            "incorrectly_abstained": sum(
                1 for row in conflict_rows if row.get("insufficient_evidence")
            ),
            "false_conflict_reported": sum(
                1 for row in non_conflict_answered if row.get("conflict_reported")
            ),
        },
        "ambiguity": {
            "guessed_referent": guessed_referent,
        },
        "multi_source": {
            "items_with_slots": slot_total,
            "all_slots_lexically_matched": slot_complete,
            "all_slots_lexically_matched_rate": rate(slot_complete, slot_total),
            "slot_count": slot_n,
            "slots_lexically_matched": slot_answered,
            "lexical_slot_match_rate": rate(slot_answered, slot_n),
            "slots_cited_gold": slot_cited,
            "slot_cited_gold_rate": rate(slot_cited, slot_n),
            "unmatched_labeled_slots": max(slot_n - slot_answered, 0),
            "items_with_forbidden_phrase": sum(
                1
                for row in rows
                if (row.get("claim_slots") or []) and row.get("forbidden_hit")
            ),
        },
        "phrase_consistency": phrase_stats,
        "repair": {
            "invocation_count": len(repair_runs),
            "invocation_rate": rate(len(repair_runs), n),
            "drift_kinds": dict(drift_kinds),
            "repair_grounded_without_cited_gold": false_grounding_repair,
        },
        "cited_gold_coverage": {
            "product_grounded": len(grounded),
            "full_gold_passage_coverage": support_counts.get("FULL_GOLD_PASSAGE_COVERAGE", 0),
            "partial_gold_passage_coverage": support_counts.get("PARTIAL_GOLD_PASSAGE_COVERAGE", 0),
            "no_gold_passage_coverage": support_counts.get("NO_GOLD_PASSAGE_COVERAGE", 0),
            "not_applicable": support_counts.get("NOT_APPLICABLE", 0),
            "product_grounded_with_full_cited_gold": grounded_full_gold,
            "product_grounded_without_cited_gold": grounded_no_gold,
        },
        "llm_calls": {
            "mean": mean([float(item) for item in call_counts if item is not None]),
        },
        "unverified": dict(unverified),
        "primary_failures": dict(primary),
        "latency": {key: summarize_latency(values, skip_first=True) for key, values in latencies.items() if values},
    }
