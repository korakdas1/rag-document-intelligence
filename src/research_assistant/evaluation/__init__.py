"""Evaluation over the same serving interfaces. Does not replace retrieval or generation."""

from research_assistant.evaluation.dataset import load_dataset, validate_dataset
from research_assistant.evaluation.metrics import (
    hit_rate_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from research_assistant.evaluation.models import EvaluationDataset, EvaluationExample
from research_assistant.evaluation.runner import EvaluationRunner

__all__ = [
    "EvaluationDataset",
    "EvaluationExample",
    "EvaluationRunner",
    "hit_rate_at_k",
    "load_dataset",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
    "validate_dataset",
]
