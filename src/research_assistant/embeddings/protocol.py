"""EmbeddingModel protocol. Implementations must not touch SQLite or vector stores."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from research_assistant.embeddings.identity import EmbeddingIdentity


class EmbeddingModel(Protocol):
    @property
    def identity(self) -> EmbeddingIdentity: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...
