"""Chunker registry."""

from __future__ import annotations

from research_assistant.chunking.config import ChunkingConfig
from research_assistant.chunking.protocol import Chunker
from research_assistant.chunking.structure import StructureAwareChunker
from research_assistant.chunking.window import WindowChunker
from research_assistant.core.errors import ChunkingError


class ChunkerRegistry:
    def __init__(self) -> None:
        self._chunkers: dict[str, Chunker] = {
            "structure": StructureAwareChunker(),
            "window": WindowChunker(),
        }

    def get(self, config: ChunkingConfig) -> Chunker:
        try:
            return self._chunkers[config.strategy]
        except KeyError as exc:
            raise ChunkingError(
                f"No chunker registered for strategy {config.strategy}",
                code="unknown_strategy",
            ) from exc
