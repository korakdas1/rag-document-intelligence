"""Domain errors for ingestion and parsing.

Expected failures are converted to IngestResult by IngestionService.
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base error for document ingestion/parsing."""

    code = "ingestion_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message


class FileValidationError(IngestionError):
    code = "invalid_file"


class UnsupportedFileTypeError(IngestionError):
    code = "unsupported_type"


class DecodeError(IngestionError):
    code = "decode_error"


class ParseError(IngestionError):
    code = "parse_error"


class ChunkingError(IngestionError):
    code = "chunking_error"


class EmbeddingError(IngestionError):
    code = "embedding_error"


class VectorStoreError(IngestionError):
    code = "vector_store_error"


class IndexingError(IngestionError):
    code = "indexing_error"


class RetrievalError(IngestionError):
    code = "retrieval_error"


class RerankError(IngestionError):
    code = "rerank_error"


class ContextError(IngestionError):
    code = "context_error"


class GenerationError(IngestionError):
    code = "generation_error"


class EvaluationError(IngestionError):
    code = "evaluation_error"


class ConfigurationError(IngestionError):
    """Invalid process configuration. Fail startup; do not silently coerce."""

    code = "invalid_config"


class DatabaseError(IngestionError):
    """SQLite cannot be used. Never delete or recreate a corrupt file."""

    code = "database_error"
