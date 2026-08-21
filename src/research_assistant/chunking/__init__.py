"""Chunking strategies. Consume ParsedDocument.blocks; do not re-parse files."""

from research_assistant.chunking.config import ChunkingConfig, default_config
from research_assistant.chunking.models import Chunk
from research_assistant.chunking.service import ChunkingResult, ChunkingService
from research_assistant.chunking.structure import StructureAwareChunker
from research_assistant.chunking.window import WindowChunker

__all__ = [
    "Chunk",
    "ChunkingConfig",
    "ChunkingResult",
    "ChunkingService",
    "StructureAwareChunker",
    "WindowChunker",
    "default_config",
]
