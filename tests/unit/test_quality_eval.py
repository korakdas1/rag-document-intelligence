"""Qualitybench dataset and metric unit tests. No model calls."""

from pathlib import Path

import pytest

from research_assistant.core.errors import EvaluationError
from research_assistant.evaluation.dataset import load_dataset, validate_dataset
from research_assistant.evaluation.models import EvaluationExample, GoldPassage, Split
from research_assistant.evaluation.quality_metrics import (
    PRODUCT_GROUNDED,
    PRODUCT_NOT_ENOUGH_EVIDENCE,
    PRODUCT_UNVERIFIED,
    key_fact_recall,
    product_status,
    quality_aggregates,
    unverified_reason,
)
from research_assistant.evaluation.quality_taxonomy import (
    CONTEXT_BUDGET_DROP,
    FALSE_ABSTENTION_WITH_GOLD_CONTEXT,
    FALSE_ANSWER_WITHOUT_SUPPORT,
    MISSING_CITATION,
    QUERY_REWRITE_ERROR,
    RETRIEVAL_MISS,
    classify_quality,
)

ROOT = Path(__file__).resolve().parents[2]
QUALITY_DATASET = ROOT / "evaluation/datasets/qualitybench_v1.jsonl"
QUALITY_CORPUS = ROOT / "evaluation/corpus/quality"


def _example(**overrides) -> EvaluationExample:
    payload = {
        "example_id": "x",
        "question": "q",
        "split": Split.TEST,
        "category": "factual",
        "answerable": True,
        "key_facts": ("42 vehicles",),
        "gold_passages": (GoldPassage("f.md", "The revenue fleet contains 42 vehicles."),),
    }
    payload.update(overrides)
    return EvaluationExample(**payload)


def test_qualitybench_loads_and_matches_corpus() -> None:
    dataset = load_dataset(QUALITY_DATASET)
    validate_dataset(dataset, corpus_dir=QUALITY_CORPUS)
    assert dataset.version == "qualitybench.v1"
    assert 40 <= len(dataset.examples) <= 80
    assert {item.split for item in dataset.examples} == {Split.DEV, Split.TEST}
    answerable = [item for item in dataset.examples if item.answerable]
    unanswerable = [item for item in dataset.examples if not item.answerable]
    assert answerable
    assert unanswerable
    assert all(item.gold_passages or item.relevant_chunk_ids for item in answerable)
    assert all(not item.gold_passages for item in unanswerable)
    slices = {item.slice_name for item in dataset.examples}
    for required in {"core", "conflict", "leak", "followup", "paraphrase", "longdoc", "subset"}:
        assert required in slices
    assert any(item.expected_conflict for item in dataset.examples)
    assert any(item.history for item in dataset.examples)
    assert any(item.paraphrase_group for item in dataset.examples)
    assert any(item.claims for item in dataset.examples)


def test_answerability_is_explicit_not_inferred() -> None:
    dataset = load_dataset(QUALITY_DATASET)
    for item in dataset.examples:
        assert item.answerable is True or item.answerable is False
        if item.answerable:
            assert item.expected_insufficient is False
        else:
            assert item.expected_insufficient is True


def test_key_fact_recall_is_substring_not_exact_match() -> None:
    assert key_fact_recall("The revenue fleet contains 42 vehicles [S1].", ["42 vehicles"]) == 1.0
    assert key_fact_recall("There are many buses.", ["42 vehicles"]) == 0.0
    assert key_fact_recall("Mira Solano directs 42 vehicles.", ["Mira Solano", "42 vehicles"]) == 1.0
    assert key_fact_recall("Mira Solano directs operations.", ["Mira Solano", "42 vehicles"]) == 0.5


def test_conflict_reported_is_generic_not_corpus_specific() -> None:
    from research_assistant.evaluation.quality_metrics import conflict_reported

    assert conflict_reported(
        "The sources conflict: one document gives 12 May [S1], while another gives 3 June [S2]."
    )
    assert not conflict_reported("Badge-tap census counts differ from infrared gate counts [S1].")
    assert not conflict_reported("The revenue fleet contains 42 vehicles [S1].")


def test_product_status_and_unverified_subtypes() -> None:
    assert product_status("valid") == PRODUCT_GROUNDED
    assert product_status("missing_citations") == PRODUCT_UNVERIFIED
    assert product_status("insufficient_evidence") == PRODUCT_NOT_ENOUGH_EVIDENCE
    assert unverified_reason(validation_status="missing_citations", key_fact_recall_value=1.0) == (
        "useful_missing_citation"
    )
    assert unverified_reason(validation_status="missing_citations", key_fact_recall_value=0.0) == (
        "wrong_missing_citation"
    )


def test_confusion_matrix_aggregates() -> None:
    examples = (
        _example(example_id="a", answerable=True, expected_insufficient=False),
        _example(example_id="b", answerable=False, expected_insufficient=True, key_facts=()),
    )
    rows = [
        {
            "example_id": "a",
            "insufficient_evidence": False,
            "product_status": PRODUCT_GROUNDED,
            "gold_in_context": True,
            "validation_status": "valid",
            "cited_chunk_ids": ["c1"],
            "timings_ms": {"retrieval_ms": 1.0, "total_ms": 2.0},
        },
        {
            "example_id": "b",
            "insufficient_evidence": True,
            "product_status": PRODUCT_NOT_ENOUGH_EVIDENCE,
            "gold_in_context": None,
            "validation_status": "insufficient_evidence",
            "cited_chunk_ids": [],
            "timings_ms": {"retrieval_ms": 1.0, "total_ms": 2.0},
        },
    ]
    metrics = quality_aggregates(rows, examples)
    assert metrics["abstention"]["true_positive"] == 1
    assert metrics["abstention"]["true_negative"] == 1
    assert metrics["abstention"]["false_positive"] == 0
    assert metrics["abstention"]["false_negative"] == 0


def test_root_cause_order_does_not_blame_generation_for_retrieval_miss() -> None:
    example = _example()
    row = {
        "expected_chunk_ids": ["gold"],
        "hybrid_ids": ["other"],
        "rerank_ids": ["other"],
        "context_chunk_ids": ["other"],
        "gold_in_context": False,
        "insufficient_evidence": True,
        "validation_status": "insufficient_evidence",
        "rewrite_error": False,
    }
    primary, _secondary = classify_quality(example, row)
    assert primary == RETRIEVAL_MISS


def test_false_abstention_only_when_gold_in_context() -> None:
    example = _example()
    row = {
        "expected_chunk_ids": ["gold"],
        "hybrid_ids": ["gold"],
        "rerank_ids": ["gold"],
        "context_chunk_ids": ["gold"],
        "gold_in_context": True,
        "insufficient_evidence": True,
        "validation_status": "insufficient_evidence",
        "rewrite_error": False,
    }
    primary, _secondary = classify_quality(example, row)
    assert primary == FALSE_ABSTENTION_WITH_GOLD_CONTEXT


def test_context_drop_before_missing_citation() -> None:
    example = _example()
    row = {
        "expected_chunk_ids": ["gold"],
        "hybrid_ids": ["gold"],
        "rerank_ids": ["gold"],
        "context_chunk_ids": ["other"],
        "gold_in_context": False,
        "insufficient_evidence": False,
        "validation_status": "missing_citations",
        "rewrite_error": False,
        "answer_text": "42 vehicles",
        "key_fact_recall": 1.0,
    }
    primary, _secondary = classify_quality(example, row)
    assert primary == CONTEXT_BUDGET_DROP


def test_false_answer_and_rewrite_and_missing_citation() -> None:
    unanswerable = _example(answerable=False, expected_insufficient=True, key_facts=())
    primary, _ = classify_quality(
        unanswerable,
        {
            "expected_chunk_ids": [],
            "hybrid_ids": [],
            "insufficient_evidence": False,
            "validation_status": "missing_citations",
            "rewrite_error": False,
        },
    )
    assert primary == FALSE_ANSWER_WITHOUT_SUPPORT
    follow = _example(history=({"question": "Who designed it?", "answer": "Dana"},))
    primary, secondary = classify_quality(
        follow,
        {"rewrite_error": True, "expected_chunk_ids": ["gold"], "hybrid_ids": ["gold"]},
    )
    assert primary == QUERY_REWRITE_ERROR
    assert "FOLLOWUP_RESOLUTION_FAILURE" in secondary
    cited_miss = _example()
    primary, _ = classify_quality(
        cited_miss,
        {
            "expected_chunk_ids": ["gold"],
            "hybrid_ids": ["gold"],
            "rerank_ids": ["gold"],
            "context_chunk_ids": ["gold"],
            "gold_in_context": True,
            "insufficient_evidence": False,
            "validation_status": "missing_citations",
            "rewrite_error": False,
            "key_fact_recall": 1.0,
            "answer_text": "42 vehicles",
        },
    )
    assert primary == MISSING_CITATION


def test_context_only_trace_does_not_count_false_answer() -> None:
    unanswerable = _example(answerable=False, expected_insufficient=True, key_facts=(), gold_passages=())
    primary, _ = classify_quality(
        unanswerable,
        {
            "expected_chunk_ids": [],
            "hybrid_ids": ["x"],
            "rewrite_error": False,
        },
    )
    assert primary is None


def test_followup_resolved_contains_requires_history() -> None:
    from research_assistant.evaluation.dataset import validate_examples

    bad = _example(expected_resolved_contains=("Dana Quill",), history=())
    with pytest.raises(EvaluationError, match="history"):
        validate_examples([bad], source="t")


def test_phrase_extra_diagnostic_set_loads() -> None:
    extra = ROOT / "evaluation/datasets/qualitybench_phrase_extra.jsonl"
    dataset = load_dataset(extra)
    validate_dataset(dataset, corpus_dir=QUALITY_CORPUS)
    assert len(dataset.examples) == 3
    assert all(item.paraphrase_group == "rtl-fleet-extra" for item in dataset.examples)
    assert all(item.split is Split.DEV for item in dataset.examples)
