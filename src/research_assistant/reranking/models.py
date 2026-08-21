"""Runtime rerank result types. Not persisted."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_assistant.retrieval.models import RetrievalHit


@dataclass(frozen=True)
class RerankDiagnostics:
    reranker_id: str
    enabled: bool
    input_count: int
    output_count: int
    batch_size: int
    truncated_count: int
    inference_ms: float
    device: str
    scoring: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "reranker_id": self.reranker_id,
            "enabled": self.enabled,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "batch_size": self.batch_size,
            "truncated_count": self.truncated_count,
            "inference_ms": round(self.inference_ms, 2),
            "device": self.device,
            "scoring": self.scoring,
        }


@dataclass(frozen=True)
class RerankResult:
    query: str
    hits: tuple[RetrievalHit, ...]
    diagnostics: RerankDiagnostics
