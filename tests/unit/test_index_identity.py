from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.indexing.identity import index_id_for


def test_same_config_same_index_id() -> None:
    embedder = HashingEmbeddingModel(dimension=32)
    left = index_id_for(embedding=embedder.identity, chunker_id="structure.v1:aaa")
    right = index_id_for(embedding=embedder.identity, chunker_id="structure.v1:aaa")
    assert left == right


def test_changed_chunker_changes_index_id() -> None:
    embedder = HashingEmbeddingModel(dimension=32)
    left = index_id_for(embedding=embedder.identity, chunker_id="structure.v1:aaa")
    right = index_id_for(embedding=embedder.identity, chunker_id="window.v1:bbb")
    assert left != right


def test_changed_embedding_changes_index_id() -> None:
    a = HashingEmbeddingModel(dimension=32)
    b = HashingEmbeddingModel(dimension=64)
    left = index_id_for(embedding=a.identity, chunker_id="structure.v1:aaa")
    right = index_id_for(embedding=b.identity, chunker_id="structure.v1:aaa")
    assert left != right
