"""Embedding models. Independent of SQLite and vector backends."""

from research_assistant.embeddings.factory import embedding_model_from_settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.embeddings.identity import EmbeddingIdentity
from research_assistant.embeddings.profiles import DEFAULT_MODEL_NAME

__all__ = [
    "DEFAULT_MODEL_NAME",
    "EmbeddingIdentity",
    "HashingEmbeddingModel",
    "embedding_model_from_settings",
]
