"""Known local embedding models and their query/document conventions."""

from __future__ import annotations

from dataclasses import dataclass

# Development default. Not claimed optimal for retrieval quality.
DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"

BGE_QUERY_INSTRUCTION = (
    "Represent this sentence for searching relevant passages: "
)


@dataclass(frozen=True)
class ModelProfile:
    query_prefix: str
    document_prefix: str
    normalize: bool
    expected_dimension: int


PROFILES: dict[str, ModelProfile] = {
    "BAAI/bge-small-en-v1.5": ModelProfile(
        query_prefix=BGE_QUERY_INSTRUCTION,
        document_prefix="",
        normalize=True,
        expected_dimension=384,
    ),
    "intfloat/e5-small-v2": ModelProfile(
        query_prefix="query: ",
        document_prefix="passage: ",
        normalize=True,
        expected_dimension=384,
    ),
    "sentence-transformers/all-MiniLM-L6-v2": ModelProfile(
        query_prefix="",
        document_prefix="",
        normalize=True,
        expected_dimension=384,
    ),
}


def profile_for(model_name: str) -> ModelProfile:
    if model_name in PROFILES:
        return PROFILES[model_name]
    return ModelProfile(
        query_prefix="",
        document_prefix="",
        normalize=True,
        expected_dimension=0,
    )
