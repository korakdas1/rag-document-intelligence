"""Core settings, errors, and shared types."""

from research_assistant.core.errors import (
    ChunkingError,
    DecodeError,
    EmbeddingError,
    FileValidationError,
    IndexingError,
    IngestionError,
    ParseError,
    RetrievalError,
    UnsupportedFileTypeError,
    VectorStoreError,
)
from research_assistant.core.settings import Settings, load_settings
from research_assistant.core.types import (
    BlockKind,
    ChunkingOutcome,
    ContentType,
    IndexingOutcome,
    IndexStatus,
    IngestOutcome,
    ParseStatus,
)

__all__ = [
    "BlockKind",
    "ChunkingError",
    "ChunkingOutcome",
    "ContentType",
    "DecodeError",
    "EmbeddingError",
    "FileValidationError",
    "IndexStatus",
    "IndexingError",
    "IndexingOutcome",
    "IngestOutcome",
    "IngestionError",
    "ParseError",
    "ParseStatus",
    "RetrievalError",
    "Settings",
    "UnsupportedFileTypeError",
    "VectorStoreError",
    "load_settings",
]
