"""Dataset validation. No retrieval."""

from pathlib import Path

import pytest

from research_assistant.core.errors import EvaluationError
from research_assistant.evaluation.dataset import load_dataset, validate_dataset
from research_assistant.evaluation.models import EvaluationExample, GoldPassage, Split


def test_ragbench_loads_and_matches_corpus() -> None:
    root = Path(__file__).resolve().parents[2]
    dataset = load_dataset(root / "evaluation/datasets/ragbench_v1.jsonl")
    validate_dataset(dataset, corpus_dir=root / "evaluation/corpus")
    assert len(dataset.examples) >= 40
    assert {item.split for item in dataset.examples} == {Split.DEV, Split.TEST}


def test_duplicate_ids_fail(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    line = (
        '{"example_id":"a","question":"q","split":"test","category":"x",'
        '"answerable":true,"gold_passages":[{"filename":"f.md","text":"t"}]}'
    )
    path.write_text(line + "\n" + line + "\n", encoding="utf-8")
    with pytest.raises(EvaluationError, match="duplicate"):
        load_dataset(path)


def test_answerable_without_gold_fails() -> None:
    example = EvaluationExample(
        example_id="x",
        question="q",
        split=Split.TEST,
        category="semantic",
        answerable=True,
    )
    with pytest.raises(EvaluationError, match="no gold"):
        validate_dataset(
            __import__("research_assistant.evaluation.models", fromlist=["EvaluationDataset"]).EvaluationDataset(
                dataset_id="t",
                version="x",
                examples=(example,),
            )
        )


def test_unanswerable_with_gold_fails() -> None:
    from research_assistant.evaluation.models import EvaluationDataset

    example = EvaluationExample(
        example_id="x",
        question="q",
        split=Split.TEST,
        category="insufficient",
        answerable=False,
        expected_insufficient=True,
        gold_passages=(GoldPassage("f.md", "hello"),),
    )
    with pytest.raises(EvaluationError, match="unanswerable"):
        validate_dataset(EvaluationDataset("t", "x", (example,)))
