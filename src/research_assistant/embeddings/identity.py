"""Embedding model identity. Distinct from chunk_id / content_hash / index_id."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingIdentity:
    """Reproducible description of how vectors were produced."""

    provider: str
    model_name: str
    revision: str
    dimension: int
    normalize: bool
    query_prefix: str
    document_prefix: str
    metric: str = "cosine"

    @property
    def embedding_model_id(self) -> str:
        payload = json.dumps(
            {
                "provider": self.provider,
                "model_name": self.model_name,
                "revision": self.revision,
                "dimension": self.dimension,
                "normalize": self.normalize,
                "query_prefix": self.query_prefix,
                "document_prefix": self.document_prefix,
                "metric": self.metric,
            },
            sort_keys=True,
        )
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        short_name = self.model_name.rsplit("/", 1)[-1]
        return f"{short_name}:{fingerprint}"

    def to_dict(self) -> dict[str, object]:
        return {
            "embedding_model_id": self.embedding_model_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "revision": self.revision,
            "dimension": self.dimension,
            "normalize": self.normalize,
            "query_prefix": self.query_prefix,
            "document_prefix": self.document_prefix,
            "metric": self.metric,
        }
