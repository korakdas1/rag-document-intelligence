"""Construct an EmbeddingModel from settings. Hashing is for tests/CI only."""

from __future__ import annotations

from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.embeddings.protocol import EmbeddingModel
from research_assistant.embeddings.sentence_transformer import SentenceTransformerEmbedding


def embedding_model_from_settings(settings: Settings) -> EmbeddingModel:
    name = settings.embedding_model_name
    if name.startswith("hashing"):
        return HashingEmbeddingModel(normalize=settings.embedding_normalize)
    return SentenceTransformerEmbedding(
        name,
        device=settings.embedding_device,
        normalize=settings.embedding_normalize,
        batch_size=settings.embedding_batch_size,
    )
