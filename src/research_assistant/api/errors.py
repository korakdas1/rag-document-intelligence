"""Stable API error contract. Never include stack traces or secrets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_assistant.core.errors import (
    ChunkingError,
    ContextError,
    FileValidationError,
    GenerationError,
    IndexingError,
    IngestionError,
    RerankError,
    RetrievalError,
    UnsupportedFileTypeError,
    VectorStoreError,
)
from research_assistant.core.resource import (
    RESOURCE_EXHAUSTED_CODE,
    RESOURCE_EXHAUSTED_MESSAGE,
    looks_like_resource_exhaustion,
)


@dataclass(frozen=True)
class ApiError(Exception):
    code: str
    message: str
    status_code: int = 400
    request_id: str = ""
    turn_id: str = ""
    session_id: str = ""

    def payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "request_id": self.request_id,
        }
        if self.turn_id:
            body["turn_id"] = self.turn_id
        if self.session_id:
            body["session_id"] = self.session_id
        return {"error": body}


_STATUS_BY_CODE = {
    "invalid_file": 400,
    "unsupported_type": 415,
    "too_large": 413,
    "empty_file": 400,
    "empty_query": 400,
    "question_too_long": 400,
    "invalid_filter": 400,
    "not_a_pdf": 400,
    "not_found": 404,
    "is_directory": 400,
    "not_a_file": 400,
    "unreadable": 400,
    "decode_error": 400,
    "parse_error": 422,
    "not_parsed": 409,
    "missing_parsed_payload": 409,
    "no_ready_documents": 409,
    "missing_index": 409,
    "chunking_error": 422,
    "indexing_error": 500,
    "embedding_error": 500,
    "resource_exhausted": 503,
    "vector_store_error": 503,
    "vector_store_unavailable": 503,
    "vector_cleanup_failed": 503,
    "source_missing": 409,
    "delete_failed": 500,
    "invalid_title": 400,
    "session_persist_failed": 500,
    "retrieval_error": 500,
    "rerank_error": 500,
    "model_unavailable": 503,
    "context_error": 500,
    "generation_error": 500,
    "timeout": 504,
    "provider_unavailable": 503,
    "invalid_model": 503,
    "invalid_api_key": 503,
    "rate_limit": 503,
    "database_busy": 503,
    "database_corrupt": 503,
    "database_error": 503,
    "invalid_config": 500,
}

_PUBLIC_MESSAGES = {
    "parse_error": "The file could not be parsed.",
    "not_a_pdf": "The file is not a valid PDF.",
    "decode_error": "The text file could not be decoded.",
    "database_busy": "The document store is busy. Retry shortly.",
    "database_corrupt": "The document store cannot be read.",
    "database_error": "The document store could not complete the request.",
    "internal_error": "An unexpected error occurred.",
    "resource_exhausted": RESOURCE_EXHAUSTED_MESSAGE,
}


def public_message(code: str, message: str) -> str:
    if looks_like_resource_exhaustion(message) or code == RESOURCE_EXHAUSTED_CODE:
        if message.startswith("Could not index"):
            return message
        return RESOURCE_EXHAUSTED_MESSAGE
    if code in _PUBLIC_MESSAGES:
        return _PUBLIC_MESSAGES[code]
    return message


def error_from_domain(exc: Exception, *, request_id: str = "") -> ApiError:
    if isinstance(exc, ApiError):
        return ApiError(
            code=exc.code,
            message=public_message(exc.code, exc.message),
            status_code=exc.status_code,
            request_id=request_id or exc.request_id,
            turn_id=exc.turn_id,
            session_id=exc.session_id,
        )
    if isinstance(exc, IngestionError):
        code = exc.code
        if looks_like_resource_exhaustion(exc.message):
            code = RESOURCE_EXHAUSTED_CODE
        status = _STATUS_BY_CODE.get(code, _default_status(exc))
        return ApiError(
            code=code,
            message=public_message(code, exc.message),
            status_code=status,
            request_id=request_id,
        )
    return ApiError(
        code="internal_error",
        message="An unexpected error occurred.",
        status_code=500,
        request_id=request_id,
    )


def _default_status(exc: IngestionError) -> int:
    if isinstance(exc, (FileValidationError, UnsupportedFileTypeError)):
        return 400
    if isinstance(exc, RetrievalError):
        return 400 if exc.code == "invalid_filter" else 500
    if isinstance(exc, RerankError):
        return 503 if exc.code == "model_unavailable" else 500
    if isinstance(exc, GenerationError):
        if exc.code == "timeout":
            return 504
        if exc.code in {"provider_unavailable", "invalid_model"}:
            return 503
        if exc.code == "empty_query":
            return 400
        return 500
    if isinstance(exc, VectorStoreError):
        return 503
    if isinstance(exc, (ChunkingError, IndexingError, ContextError)):
        return 503 if getattr(exc, "code", "") == RESOURCE_EXHAUSTED_CODE else 500
    return 500
