"""Exact metric definitions. Tiny hand-computed cases."""

from research_assistant.evaluation.metrics import (
    abstention_counts,
    exact_match,
    hit_rate_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    percentile,
    precision_at_k,
    rate,
    recall_at_k,
    reciprocal_rank,
    token_f1,
)


def test_recall_at_k_basic() -> None:
    retrieved = ["a", "b", "c", "d"]
    relevant = {"a", "c"}
    assert recall_at_k(retrieved, relevant, 1) == 0.5
    assert recall_at_k(retrieved, relevant, 3) == 1.0
    assert recall_at_k(retrieved, relevant, 10) == 1.0


def test_recall_empty_relevant_is_none() -> None:
    assert recall_at_k(["a"], [], 5) is None


def test_precision_at_k_uses_k_denominator() -> None:
    retrieved = ["a", "x", "y"]
    relevant = {"a"}
    assert precision_at_k(retrieved, relevant, 5) == 0.2


def test_hit_rate_and_mrr() -> None:
    retrieved = ["x", "gold", "y"]
    relevant = {"gold"}
    assert hit_rate_at_k(retrieved, relevant, 1) == 0.0
    assert hit_rate_at_k(retrieved, relevant, 2) == 1.0
    assert reciprocal_rank(retrieved, relevant) == 0.5
    assert reciprocal_rank(["x", "y"], relevant) == 0.0
    assert mean_reciprocal_rank([1.0, 0.5, 0.0]) == 0.5


def test_ndcg_binary() -> None:
    relevant = {"a"}
    perfect = ndcg_at_k(["a", "b"], relevant, 2)
    worse = ndcg_at_k(["b", "a"], relevant, 2)
    assert perfect == 1.0
    assert worse is not None and worse < 1.0


def test_abstention_rates() -> None:
    tp, fp, fn, tn = abstention_counts(
        [True, True, False, False],
        [True, False, True, False],
    )
    assert (tp, fp, fn, tn) == (1, 1, 1, 1)
    assert rate(tp, tp + fp) == 0.5
    assert rate(fn, tp + fn) == 0.5


def test_token_f1_and_exact_match() -> None:
    assert exact_match("2017", "2017") == 1.0
    assert exact_match("in 2017.", "2017") == 0.0
    f1 = token_f1("quadratic complexity", "quadratic")
    assert f1 is not None and 0 < f1 < 1


def test_percentile_requires_samples() -> None:
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([], 95) is None
