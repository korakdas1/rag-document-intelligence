"""Lexical index identity. Ranking config must be inspectable even when
the index is rebuilt from SQLite on each cache miss."""

from __future__ import annotations

import hashlib
import json

from research_assistant.retrieval.tokenize import TOKENIZER_ID

LEXICAL_SCHEMA_VERSION = 1
LEXICAL_BACKEND = "bm25.v1"


def lexical_index_id_for(
    *,
    chunker_id: str,
    tokenizer_id: str = TOKENIZER_ID,
    k1: float,
    b: float,
    schema_version: int = LEXICAL_SCHEMA_VERSION,
    backend: str = LEXICAL_BACKEND,
) -> str:
    payload = json.dumps(
        {
            "backend": backend,
            "b": round(b, 6),
            "chunker_id": chunker_id,
            "k1": round(k1, 6),
            "schema_version": schema_version,
            "tokenizer_id": tokenizer_id,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
