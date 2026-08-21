"""Construct a Reranker from settings. Overlap is for tests/CI only."""

from __future__ import annotations

from research_assistant.core.settings import Settings
from research_assistant.reranking.overlap import OverlapReranker
from research_assistant.reranking.protocol import Reranker


def reranker_from_settings(settings: Settings) -> Reranker:
    name = settings.reranker_model_name.strip()
    if name.startswith("overlap") or name == "hashing":
        return OverlapReranker(max_length=settings.reranker_max_length)
    from research_assistant.reranking.cross_encoder import CrossEncoderReranker

    return CrossEncoderReranker(
        name,
        device=settings.reranker_device,
        batch_size=settings.reranker_batch_size,
        max_length=settings.reranker_max_length,
    )
