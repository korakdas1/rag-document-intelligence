"""Evaluation entities. File-based, not SQLite tables."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from research_assistant.evaluation.identity import METRICS_SCHEMA


class Split(StrEnum):
    DEV = "dev"
    TEST = "test"


class EvalStage(StrEnum):
    RETRIEVAL = "retrieval"
    RERANK = "rerank"
    CONTEXT = "context"
    GENERATION = "generation"
    FULL = "full"


@dataclass(frozen=True)
class GoldPassage:
    filename: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"filename": self.filename, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoldPassage:
        return cls(filename=str(data["filename"]), text=str(data["text"]))


@dataclass(frozen=True)
class QualityClaim:
    claim_id: str
    text: str
    filename: str = ""
    gold_text: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "filename": self.filename,
            "gold_text": self.gold_text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityClaim:
        return cls(
            claim_id=str(data.get("claim_id") or ""),
            text=str(data.get("text") or ""),
            filename=str(data.get("filename") or ""),
            gold_text=str(data.get("gold_text") or data.get("gold_passage") or ""),
        )


@dataclass(frozen=True)
class EvaluationExample:
    example_id: str
    question: str
    split: Split
    category: str
    answerable: bool
    relevant_filenames: tuple[str, ...] = ()
    gold_passages: tuple[GoldPassage, ...] = ()
    relevant_chunk_ids: tuple[str, ...] = ()
    reference_answer: str | None = None
    expected_insufficient: bool = False
    expected_conflict: bool = False
    expected_injection: bool = False
    notes: str = ""
    tags: tuple[str, ...] = ()
    key_facts: tuple[str, ...] = ()
    forbidden_facts: tuple[str, ...] = ()
    claims: tuple[QualityClaim, ...] = ()
    history: tuple[dict[str, Any], ...] = ()
    paraphrase_group: str = ""
    slice_name: str = ""
    selected_filenames: tuple[str, ...] = ()
    expected_resolved_contains: tuple[str, ...] = ()
    expected_resolved_must_not: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "example_id": self.example_id,
            "question": self.question,
            "split": self.split.value,
            "category": self.category,
            "answerable": self.answerable,
            "relevant_filenames": list(self.relevant_filenames),
            "gold_passages": [item.to_dict() for item in self.gold_passages],
            "relevant_chunk_ids": list(self.relevant_chunk_ids),
            "reference_answer": self.reference_answer,
            "expected_insufficient": self.expected_insufficient,
            "expected_conflict": self.expected_conflict,
            "expected_injection": self.expected_injection,
            "notes": self.notes,
            "tags": list(self.tags),
        }
        if self.key_facts:
            payload["key_facts"] = list(self.key_facts)
        if self.forbidden_facts:
            payload["forbidden_facts"] = list(self.forbidden_facts)
        if self.claims:
            payload["claims"] = [item.to_dict() for item in self.claims]
        if self.history:
            payload["history"] = list(self.history)
        if self.paraphrase_group:
            payload["paraphrase_group"] = self.paraphrase_group
        if self.slice_name:
            payload["slice"] = self.slice_name
        if self.selected_filenames:
            payload["selected_filenames"] = list(self.selected_filenames)
        if self.expected_resolved_contains:
            payload["expected_resolved_contains"] = list(self.expected_resolved_contains)
        if self.expected_resolved_must_not:
            payload["expected_resolved_must_not"] = list(self.expected_resolved_must_not)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationExample:
        split_raw = str(data.get("split") or Split.TEST.value)
        passages = tuple(GoldPassage.from_dict(item) for item in data.get("gold_passages") or [])
        filenames = tuple(str(name) for name in data.get("relevant_filenames") or ())
        if not filenames:
            filenames = tuple(dict.fromkeys(item.filename for item in passages))
        claims = tuple(QualityClaim.from_dict(item) for item in data.get("claims") or [])
        history = tuple(item for item in data.get("history") or [] if isinstance(item, dict))
        return cls(
            example_id=str(data["example_id"]),
            question=str(data["question"]),
            split=Split(split_raw),
            category=str(data.get("category") or "unspecified"),
            answerable=bool(data.get("answerable", True)),
            relevant_filenames=filenames,
            gold_passages=passages,
            relevant_chunk_ids=tuple(str(item) for item in data.get("relevant_chunk_ids") or ()),
            reference_answer=data.get("reference_answer"),
            expected_insufficient=bool(data.get("expected_insufficient", False)),
            expected_conflict=bool(data.get("expected_conflict", False)),
            expected_injection=bool(data.get("expected_injection", False)),
            notes=str(data.get("notes") or ""),
            tags=tuple(str(item) for item in data.get("tags") or ()),
            key_facts=tuple(str(item) for item in data.get("key_facts") or ()),
            forbidden_facts=tuple(str(item) for item in data.get("forbidden_facts") or ()),
            claims=claims,
            history=history,
            paraphrase_group=str(data.get("paraphrase_group") or ""),
            slice_name=str(data.get("slice") or ""),
            selected_filenames=tuple(str(item) for item in data.get("selected_filenames") or ()),
            expected_resolved_contains=tuple(
                str(item) for item in data.get("expected_resolved_contains") or ()
            ),
            expected_resolved_must_not=tuple(
                str(item) for item in data.get("expected_resolved_must_not") or ()
            ),
        )


@dataclass(frozen=True)
class EvaluationDataset:
    dataset_id: str
    version: str
    examples: tuple[EvaluationExample, ...]
    description: str = ""
    source_sha256: str | None = None

    def filter_split(self, split: Split | str | None) -> tuple[EvaluationExample, ...]:
        if split is None:
            return self.examples
        wanted = Split(split) if not isinstance(split, Split) else split
        return tuple(item for item in self.examples if item.split is wanted)


@dataclass
class ResolvedGold:
    example_id: str
    chunk_ids: set[str]
    document_ids: set[str]
    unmatched_passages: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalScores:
    recall_at_1: float | None
    recall_at_3: float | None
    recall_at_5: float | None
    recall_at_10: float | None
    recall_at_20: float | None
    mrr: float | None
    precision_at_5: float | None
    hit_rate_at_1: float | None
    hit_rate_at_5: float | None
    ndcg_at_10: float | None
    document_recall_at_5: float | None
    document_recall_at_10: float | None

    def to_dict(self) -> dict[str, float | None]:
        return {
            "recall@1": self.recall_at_1,
            "recall@3": self.recall_at_3,
            "recall@5": self.recall_at_5,
            "recall@10": self.recall_at_10,
            "recall@20": self.recall_at_20,
            "mrr": self.mrr,
            "precision@5": self.precision_at_5,
            "hit_rate@1": self.hit_rate_at_1,
            "hit_rate@5": self.hit_rate_at_5,
            "ndcg@10": self.ndcg_at_10,
            "document_recall@5": self.document_recall_at_5,
            "document_recall@10": self.document_recall_at_10,
        }


@dataclass(frozen=True)
class AbstentionScores:
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    precision: float | None
    recall: float | None
    false_answer_rate: float | None
    false_abstention_rate: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "true_negative": self.true_negative,
            "precision": self.precision,
            "recall": self.recall,
            "false_answer_rate": self.false_answer_rate,
            "false_abstention_rate": self.false_abstention_rate,
        }


@dataclass
class ExampleTrace:
    example_id: str
    question: str
    split: str
    category: str
    expected_chunk_ids: list[str]
    expected_filenames: list[str]
    dense_ids: list[str] = field(default_factory=list)
    lexical_ids: list[str] = field(default_factory=list)
    hybrid_ids: list[str] = field(default_factory=list)
    rerank_ids: list[str] = field(default_factory=list)
    context_chunk_ids: list[str] = field(default_factory=list)
    context_citation_ids: list[str] = field(default_factory=list)
    contribution: str | None = None
    answer_text: str | None = None
    validation_status: str | None = None
    insufficient_evidence: bool | None = None
    cited_chunk_ids: list[str] = field(default_factory=list)
    invalid_citation_ids: list[str] = field(default_factory=list)
    retrieval_scores: dict[str, float | None] = field(default_factory=dict)
    rerank_scores: dict[str, float | None] = field(default_factory=dict)
    gold_chunk_selected: bool | None = None
    context_gold_chunk_recall: float | None = None
    candidate_recall: float | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    failure_categories: list[str] = field(default_factory=list)
    reference_token_f1: float | None = None
    cited_gold_passage_recall: float | None = None
    judge: dict[str, Any] | None = None
    cached_generation: bool = False
    context_blocks: list[dict[str, Any]] = field(default_factory=list)
    cited_passages: list[dict[str, Any]] = field(default_factory=list)
    gold_passages: list[dict[str, str]] = field(default_factory=list)
    rerank_gold_passage_hits: list[bool] = field(default_factory=list)
    rendered_gold_passage_hits: list[bool] = field(default_factory=list)
    rendered_gold_any: bool | None = None
    rendered_gold_all: bool | None = None
    rendered_gold_passage_recall: float | None = None
    cited_gold_passage_hits: list[bool] = field(default_factory=list)
    cited_gold_any: bool | None = None
    cited_gold_all: bool | None = None
    cited_gold_coverage_class: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics_schema": METRICS_SCHEMA,
            "rerank_gold_passage_hits": self.rerank_gold_passage_hits,
            "context_blocks": self.context_blocks,
            "cited_passages": self.cited_passages,
            "gold_passages": self.gold_passages,
            "rendered_gold_passage_hits": self.rendered_gold_passage_hits,
            "rendered_gold_any": self.rendered_gold_any,
            "rendered_gold_all": self.rendered_gold_all,
            "rendered_gold_passage_recall": self.rendered_gold_passage_recall,
            "cited_gold_passage_hits": self.cited_gold_passage_hits,
            "cited_gold_any": self.cited_gold_any,
            "cited_gold_all": self.cited_gold_all,
            "cited_gold_coverage_class": self.cited_gold_coverage_class,
            "example_id": self.example_id,
            "question": self.question,
            "split": self.split,
            "category": self.category,
            "expected_chunk_ids": self.expected_chunk_ids,
            "expected_filenames": self.expected_filenames,
            "dense_ids": self.dense_ids,
            "lexical_ids": self.lexical_ids,
            "hybrid_ids": self.hybrid_ids,
            "rerank_ids": self.rerank_ids,
            "context_chunk_ids": self.context_chunk_ids,
            "context_citation_ids": self.context_citation_ids,
            "contribution": self.contribution,
            "answer_text": self.answer_text,
            "validation_status": self.validation_status,
            "insufficient_evidence": self.insufficient_evidence,
            "cited_chunk_ids": self.cited_chunk_ids,
            "invalid_citation_ids": self.invalid_citation_ids,
            "retrieval_scores": self.retrieval_scores,
            "rerank_scores": self.rerank_scores,
            "gold_chunk_selected": self.gold_chunk_selected,
            "context_gold_chunk_recall": self.context_gold_chunk_recall,
            "candidate_recall": self.candidate_recall,
            "timings_ms": self.timings_ms,
            "failure_categories": self.failure_categories,
            "reference_token_f1": self.reference_token_f1,
            "cited_gold_passage_recall": self.cited_gold_passage_recall,
            "judge": self.judge,
            "cached_generation": self.cached_generation,
        }
