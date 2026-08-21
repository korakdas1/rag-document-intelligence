"""Reranker identity. Distinct from query text and from embedding_model_id."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RerankerIdentity:
    """Reproducible description of how rerank scores were produced."""

    provider: str
    model_name: str
    revision: str
    max_length: int
    batch_size: int
    scoring: str
    device: str = "cpu"

    @property
    def reranker_id(self) -> str:
        payload = json.dumps(
            {
                "provider": self.provider,
                "model_name": self.model_name,
                "revision": self.revision,
                "max_length": self.max_length,
                "batch_size": self.batch_size,
                "scoring": self.scoring,
            },
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        short_name = self.model_name.rsplit("/", 1)[-1]
        return f"{short_name}:{fingerprint}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "reranker_id": self.reranker_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "revision": self.revision,
            "max_length": self.max_length,
            "batch_size": self.batch_size,
            "scoring": self.scoring,
            "device": self.device,
        }
