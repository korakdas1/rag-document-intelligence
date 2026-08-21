"""Indexing package. Vector backends and index orchestration."""

from research_assistant.indexing.identity import index_id_for
from research_assistant.indexing.models import IndexMetadata, VectorHit, VectorPayload

__all__ = [
    "IndexMetadata",
    "VectorHit",
    "VectorPayload",
    "index_id_for",
]
