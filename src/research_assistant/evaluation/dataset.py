"""JSONL dataset load and validation. Gold is filename + passage, not retriever output."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from research_assistant.core.errors import EvaluationError
from research_assistant.evaluation.models import (
    EvaluationDataset,
    EvaluationExample,
    GoldPassage,
    Split,
)

ALLOWED_SPLITS = {item.value for item in Split}
DATASET_VERSION = "ragbench.v1"


def load_dataset(path: Path | str) -> EvaluationDataset:
    target = Path(path)
    if not target.is_file():
        raise EvaluationError(f"Dataset not found: {target}", code="dataset_missing")
    examples: list[EvaluationExample] = []
    with target.open(encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text or text.startswith("#"):
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise EvaluationError(
                    f"{target}:{line_no} is not valid JSON",
                    code="malformed_dataset",
                ) from exc
            if not isinstance(payload, dict):
                raise EvaluationError(
                    f"{target}:{line_no} must be a JSON object",
                    code="malformed_dataset",
                )
            try:
                examples.append(EvaluationExample.from_dict(payload))
            except (KeyError, ValueError) as exc:
                raise EvaluationError(
                    f"{target}:{line_no} is not a valid example: {exc}",
                    code="malformed_dataset",
                ) from exc
    dataset_id = target.stem
    validate_examples(examples, source=str(target))
    version = "qualitybench.v1" if dataset_id.startswith("qualitybench") else DATASET_VERSION
    return EvaluationDataset(
        dataset_id=dataset_id,
        version=version,
        examples=tuple(examples),
        description=f"Loaded from {target}",
    )


def validate_dataset(
    dataset: EvaluationDataset,
    *,
    corpus_dir: Path | None = None,
) -> None:
    validate_examples(dataset.examples, source=dataset.dataset_id)
    if corpus_dir is not None:
        validate_against_corpus(dataset.examples, corpus_dir)


def validate_examples(
    examples: Sequence[EvaluationExample],
    *,
    source: str = "dataset",
) -> None:
    if not examples:
        raise EvaluationError(f"{source} contains no examples", code="empty_dataset")
    seen: set[str] = set()
    for example in examples:
        if not example.example_id.strip():
            raise EvaluationError("example_id is empty", code="invalid_example")
        if example.example_id in seen:
            raise EvaluationError(
                f"duplicate example_id {example.example_id!r}",
                code="duplicate_example_id",
            )
        seen.add(example.example_id)
        if not example.question.strip():
            raise EvaluationError(
                f"{example.example_id}: question is empty",
                code="empty_question",
            )
        if example.split.value not in ALLOWED_SPLITS:
            raise EvaluationError(
                f"{example.example_id}: invalid split {example.split!r}",
                code="invalid_split",
            )
        if example.answerable and example.expected_insufficient:
            raise EvaluationError(
                f"{example.example_id}: answerable items cannot expect insufficient evidence",
                code="impossible_relevance",
            )
        if example.answerable and not example.gold_passages and not example.relevant_chunk_ids:
            raise EvaluationError(
                f"{example.example_id}: answerable item has no gold evidence",
                code="impossible_relevance",
            )
        if not example.answerable and example.gold_passages:
            raise EvaluationError(
                f"{example.example_id}: unanswerable item has gold passages",
                code="impossible_relevance",
            )
        for passage in example.gold_passages:
            _validate_passage(example.example_id, passage)
        if example.answerable and example.expected_resolved_contains and not example.history:
            raise EvaluationError(
                f"{example.example_id}: expected_resolved_contains requires history",
                code="invalid_example",
            )


def validate_against_corpus(
    examples: Sequence[EvaluationExample],
    corpus_dir: Path,
) -> None:
    if not corpus_dir.is_dir():
        raise EvaluationError(f"Corpus directory missing: {corpus_dir}", code="corpus_missing")
    files = {path.name: path.read_text(encoding="utf-8") for path in corpus_dir.iterdir() if path.is_file()}
    for example in examples:
        for name in example.relevant_filenames:
            if name not in files:
                raise EvaluationError(
                    f"{example.example_id}: relevant filename {name!r} is not in the corpus",
                    code="invalid_filename",
                )
        for name in example.selected_filenames:
            if name not in files:
                raise EvaluationError(
                    f"{example.example_id}: selected filename {name!r} is not in the corpus",
                    code="invalid_filename",
                )
        for passage in example.gold_passages:
            body = files.get(passage.filename)
            if body is None:
                raise EvaluationError(
                    f"{example.example_id}: gold filename {passage.filename!r} is not in the corpus",
                    code="invalid_filename",
                )
            if _normalize(passage.text) not in _normalize(body):
                raise EvaluationError(
                    f"{example.example_id}: gold passage not found in {passage.filename}",
                    code="gold_passage_missing",
                )


def _validate_passage(example_id: str, passage: GoldPassage) -> None:
    if not passage.filename.strip():
        raise EvaluationError(f"{example_id}: gold passage filename is empty", code="invalid_filename")
    if not passage.text.strip():
        raise EvaluationError(f"{example_id}: gold passage text is empty", code="empty_gold_passage")


def _normalize(text: str) -> str:
    return " ".join(text.split())
