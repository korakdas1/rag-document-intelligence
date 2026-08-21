from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.embeddings.identity import EmbeddingIdentity
from research_assistant.embeddings.profiles import BGE_QUERY_INSTRUCTION, profile_for
from research_assistant.core.errors import EmbeddingError
import math
import pytest


def test_batch_and_query_dimension_consistency() -> None:
    model = HashingEmbeddingModel(dimension=32)
    docs = model.embed_documents(["alpha beta", "gamma"])
    query = model.embed_query("alpha")
    assert len(docs) == 2
    assert all(len(row) == 32 for row in docs)
    assert len(query) == 32
    assert model.identity.dimension == 32


def test_normalized_vectors_have_unit_norm() -> None:
    model = HashingEmbeddingModel(dimension=32, normalize=True)
    vector = model.embed_query("neural network training")
    norm = math.sqrt(sum(value * value for value in vector))
    assert abs(norm - 1.0) < 1e-6


def test_model_id_is_stable() -> None:
    first = HashingEmbeddingModel(dimension=32).identity.embedding_model_id
    second = HashingEmbeddingModel(dimension=32).identity.embedding_model_id
    assert first == second
    other = HashingEmbeddingModel(dimension=64).identity.embedding_model_id
    assert first != other


def test_empty_text_is_rejected() -> None:
    model = HashingEmbeddingModel()
    with pytest.raises(EmbeddingError) as exc:
        model.embed_query("   ")
    assert exc.value.code == "empty_text"


def test_bge_profile_has_query_instruction_only() -> None:
    profile = profile_for("BAAI/bge-small-en-v1.5")
    assert profile.query_prefix == BGE_QUERY_INSTRUCTION
    assert profile.document_prefix == ""
    assert profile.normalize is True
    assert profile.expected_dimension == 384


def test_embedding_identity_includes_prefixes() -> None:
    left = EmbeddingIdentity(
        provider="sentence-transformers",
        model_name="BAAI/bge-small-en-v1.5",
        revision="v1.5",
        dimension=384,
        normalize=True,
        query_prefix="q:",
        document_prefix="",
    )
    right = EmbeddingIdentity(
        provider="sentence-transformers",
        model_name="BAAI/bge-small-en-v1.5",
        revision="v1.5",
        dimension=384,
        normalize=True,
        query_prefix="",
        document_prefix="",
    )
    assert left.embedding_model_id != right.embedding_model_id
