"""Aggregate traces into reportable metric tables."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any

from research_assistant.evaluation.latency import summarize_latency
from research_assistant.evaluation.metrics import (
    abstention_counts,
    mean,
    rate,
)
from research_assistant.evaluation.models import AbstentionScores, EvaluationExample, ExampleTrace


def retrieval_table(traces: Sequence[ExampleTrace], field: str = "retrieval_scores") -> dict[str, float | None]:
    keys = [
        "recall@1",
        "recall@3",
        "recall@5",
        "recall@10",
        "recall@20",
        "mrr",
        "precision@5",
        "hit_rate@1",
        "hit_rate@5",
        "ndcg@10",
        "document_recall@5",
        "document_recall@10",
    ]
    out: dict[str, float | None] = {}
    for key in keys:
        values = [trace_scores(trace, field).get(key) for trace in traces]
        averaged = mean(values)
        out[key] = round(averaged, 4) if averaged is not None else None
    out["n"] = float(len(traces))
    out["n_with_gold"] = float(
        sum(1 for trace in traces if trace.expected_chunk_ids)
    )
    return out


def by_category(traces: Sequence[ExampleTrace], field: str = "retrieval_scores") -> dict[str, dict[str, float | None]]:
    groups: dict[str, list[ExampleTrace]] = defaultdict(list)
    for trace in traces:
        groups[trace.category].append(trace)
    return {name: retrieval_table(items, field) for name, items in sorted(groups.items())}


def contribution_summary(traces: Sequence[ExampleTrace]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for trace in traces:
        if trace.contribution:
            counts[trace.contribution] += 1
    return dict(counts)


def context_summary(traces: Sequence[ExampleTrace]) -> dict[str, float | None]:
    hits = [1.0 if trace.context_gold_hit else 0.0 for trace in traces if trace.context_gold_hit is not None]
    recalls = [trace.context_evidence_recall for trace in traces]
    candidates = [trace.candidate_recall for trace in traces]
    return {
        "n": float(len(traces)),
        "context_gold_hit_rate": _round(mean(hits)),
        "context_evidence_recall": _round(mean(recalls)),
        "candidate_recall": _round(mean(candidates)),
    }


def citation_summary(traces: Sequence[ExampleTrace], examples: Sequence[EvaluationExample]) -> dict[str, float | None]:
    by_id = {item.example_id: item for item in examples}
    n = len(traces)
    valid_only = 0
    invalid = 0
    missing = 0
    malformed = 0
    covered = 0
    answerable_substantive = 0
    support_scores: list[float | None] = []
    for trace in traces:
        example = by_id[trace.example_id]
        status = trace.validation_status
        if status == "invalid_citation":
            invalid += 1
        elif status == "missing_citations":
            missing += 1
        elif status == "malformed_output":
            malformed += 1
        if status not in {"invalid_citation", "malformed_output"} and not trace.invalid_citation_ids:
            valid_only += 1
        if example.answerable and not trace.insufficient_evidence:
            answerable_substantive += 1
            if trace.cited_chunk_ids:
                covered += 1
        support_scores.append(trace.lexical_citation_support)
    return {
        "n": float(n),
        "valid_citation_rate": rate(valid_only, n),
        "invalid_citation_count": float(invalid),
        "missing_citation_count": float(missing),
        "malformed_count": float(malformed),
        "citation_coverage": rate(covered, answerable_substantive),
        "lexical_citation_support": _round(mean(support_scores)),
    }


def abstention_summary(
    traces: Sequence[ExampleTrace],
    examples: Sequence[EvaluationExample],
) -> dict[str, Any]:
    by_id = {item.example_id: item for item in examples}
    expected = []
    predicted = []
    for trace in traces:
        if trace.insufficient_evidence is None:
            continue
        example = by_id[trace.example_id]
        expected.append(example.expected_insufficient)
        predicted.append(bool(trace.insufficient_evidence))
    tp, fp, fn, tn = abstention_counts(expected, predicted)
    scores = AbstentionScores(
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        true_negative=tn,
        precision=rate(tp, tp + fp),
        recall=rate(tp, tp + fn),
        false_answer_rate=rate(fn, tp + fn),
        false_abstention_rate=rate(fp, fp + tn),
    )
    return scores.to_dict()


def failure_summary(traces: Sequence[ExampleTrace]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for trace in traces:
        counts.update(trace.failure_categories)
    return dict(counts)


def latency_summary(traces: Sequence[ExampleTrace]) -> dict[str, Any]:
    keys = [
        "dense_ms",
        "lexical_ms",
        "fusion_ms",
        "retrieval_ms",
        "rerank_ms",
        "context_ms",
        "generation_ms",
        "total_ms",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        values = [trace.timings_ms[key] for trace in traces if key in trace.timings_ms]
        if values:
            out[key] = summarize_latency(values, skip_first=True)
    return out


def trace_scores(trace: ExampleTrace, field: str) -> dict[str, float | None]:
    payload = getattr(trace, field)
    return payload if isinstance(payload, dict) else {}


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)
