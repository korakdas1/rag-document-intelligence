"""Deterministic lexical hashing embedder for tests. Not a retrieval model."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

from research_assistant.core.errors import EmbeddingError
from research_assistant.embeddings.identity import EmbeddingIdentity

_TOKEN = re.compile(r"[a-z0-9]+")


class HashingEmbeddingModel:
    """Bag-of-tokens hashing into a fixed dense vector. CPU-only, no downloads."""

    def __init__(self, *, dimension: int = 32, normalize: bool = True) -> None:
        if dimension < 8:
            raise EmbeddingError(
                "HashingEmbeddingModel dimension must be >= 8",
                code="invalid_dimension",
            )
        self._dimension = dimension
        self._normalize = normalize
        self._identity = EmbeddingIdentity(
            provider="hashing",
            model_name="hashing.v1",
            revision="v1",
            dimension=dimension,
            normalize=normalize,
            query_prefix="",
            document_prefix="",
            metric="cosine",
        )

    @property
    def identity(self) -> EmbeddingIdentity:
        return self._identity

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text, kind="document") for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text, kind="query")

    def _embed_one(self, text: str, *, kind: str) -> list[float]:
        if not text or not text.strip():
            raise EmbeddingError(
                f"Refusing to embed empty {kind} text",
                code="empty_text",
            )
        vec = [0.0] * self._dimension
        for token in _TOKEN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[index] += sign
        if self._normalize:
            return _l2_normalize(vec)
        return vec


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        # Empty token set after stripping symbols: still a valid non-zero vector.
        out = [0.0] * len(vector)
        out[0] = 1.0
        return out
    return [value / norm for value in vector]
