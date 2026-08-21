"""Index identity: embedding config + chunker + metric + schema must not mix."""

from __future__ import annotations

import hashlib
import json

from research_assistant.embeddings.identity import EmbeddingIdentity

VECTOR_SCHEMA_VERSION = 1
DEFAULT_METRIC = "cosine"


def index_id_for(
    *,
    embedding: EmbeddingIdentity,
    chunker_id: str,
    metric: str = DEFAULT_METRIC,
    schema_version: int = VECTOR_SCHEMA_VERSION,
) -> str:
    payload = json.dumps(
        {
            "embedding_model_id": embedding.embedding_model_id,
            "dimension": embedding.dimension,
            "normalize": embedding.normalize,
            "metric": metric,
            "chunker_id": chunker_id,
            "schema_version": schema_version,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return digest


def collection_name_for(index_id: str) -> str:
    return f"idx_{index_id}"
