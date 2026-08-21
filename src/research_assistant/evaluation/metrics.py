"""Independently testable IR and generation metrics. No network."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)?", re.IGNORECASE)


def recall_at_k(retrieved: Sequence[str], relevant: Sequence[str] | set[str], k: int) -> float | None:
    """|top_k ∩ R| / |R|. None if R is empty. Ranks are the list order (1-based)."""
    gold = _unique(relevant)
    if not gold:
        return None
    if k < 1:
        raise ValueError("k must be >= 1")
    hit = set(list(retrieved)[:k]) & gold
    return len(hit) / len(gold)


def precision_at_k(retrieved: Sequence[str], relevant: Sequence[str] | set[str], k: int) -> float | None:
    """|top_k ∩ R| / k. None if R is empty."""
    gold = _unique(relevant)
    if not gold:
        return None
    if k < 1:
        raise ValueError("k must be >= 1")
    return len(set(list(retrieved)[:k]) & gold) / k


def hit_rate_at_k(retrieved: Sequence[str], relevant: Sequence[str] | set[str], k: int) -> float | None:
    """1 if any relevant item is in top-k, else 0. None if R is empty."""
    gold = _unique(relevant)
    if not gold:
        return None
    if k < 1:
        raise ValueError("k must be >= 1")
    return 1.0 if set(list(retrieved)[:k]) & gold else 0.0


def reciprocal_rank(retrieved: Sequence[str], relevant: Sequence[str] | set[str]) -> float | None:
    """1/rank of first relevant hit (1-based). 0 if missing. None if R is empty."""
    gold = _unique(relevant)
    if not gold:
        return None
    for index, item in enumerate(retrieved, start=1):
        if item in gold:
            return 1.0 / index
    return 0.0


def mean_reciprocal_rank(ranks: Sequence[float | None]) -> float | None:
    values = [item for item in ranks if item is not None]
    if not values:
        return None
    return sum(values) / len(values)


def ndcg_at_k(retrieved: Sequence[str], relevant: Sequence[str] | set[str], k: int) -> float | None:
    """Binary nDCG@k. None if R is empty."""
    gold = _unique(relevant)
    if not gold:
        return None
    if k < 1:
        raise ValueError("k must be >= 1")
    dcg = 0.0
    for index, item in enumerate(list(retrieved)[:k], start=1):
        if item in gold:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(gold), k)
    idcg = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def mean(values: Sequence[float | None]) -> float | None:
    present = [item for item in values if item is not None]
    if not present:
        return None
    return sum(present) / len(present)


def percentile(values: Sequence[float], p: float) -> float | None:
    """Nearest-rank percentile. Caller must not request p95 on tiny n."""
    if not values:
        return None
    if not 0 <= p <= 100:
        raise ValueError("percentile must be in [0, 100]")
    ordered = sorted(values)
    if p == 0:
        return ordered[0]
    rank = math.ceil((p / 100) * len(ordered)) - 1
    rank = min(max(rank, 0), len(ordered) - 1)
    return ordered[rank]


def token_f1(predicted: str, reference: str) -> float | None:
    """Normalized token F1. None if reference is empty."""
    ref = _tokens(reference)
    if not ref:
        return None
    pred = _tokens(predicted)
    if not pred:
        return 0.0
    overlap = len(ref & pred)
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred)
    recall = overlap / len(ref)
    return 2 * precision * recall / (precision + recall)


def exact_match(predicted: str, reference: str) -> float | None:
    if not (reference or "").strip():
        return None
    return 1.0 if _normalize(predicted) == _normalize(reference) else 0.0


def abstention_counts(
    expected_insufficient: Sequence[bool],
    predicted_insufficient: Sequence[bool],
) -> tuple[int, int, int, int]:
    if len(expected_insufficient) != len(predicted_insufficient):
        raise ValueError("abstention sequences must be the same length")
    tp = fp = fn = tn = 0
    for expected, predicted in zip(expected_insufficient, predicted_insufficient, strict=True):
        if expected and predicted:
            tp += 1
        elif not expected and predicted:
            fp += 1
        elif expected and not predicted:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _unique(items: Sequence[str] | set[str]) -> set[str]:
    return {str(item) for item in items if str(item)}


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(text or "")}


def _normalize(text: str) -> str:
    return " ".join(_tokens(text))
