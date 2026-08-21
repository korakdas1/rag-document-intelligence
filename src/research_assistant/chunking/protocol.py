"""Chunker protocol. Implementations must not touch SQLite or embeddings."""

from __future__ import annotations

from typing import Protocol

from research_assistant.chunking.config import ChunkingConfig
from research_assistant.chunking.models import Chunk
from research_assistant.parsing.models import ParsedDocument


class Chunker(Protocol):
    @property
    def strategy_name(self) -> str: ...

    def chunk(
        self, parsed: ParsedDocument, config: ChunkingConfig
    ) -> tuple[Chunk, ...]: ...
