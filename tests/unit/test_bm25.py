from research_assistant.retrieval.bm25 import BM25Index
from research_assistant.retrieval.tokenize import tokenize


def test_exact_identifier_ranks_first() -> None:
    docs = [
        ("a", tokenize("The transformer architecture uses self-attention.")),
        ("b", tokenize("System error code ERR_CONNECTION_REFUSED occurs.")),
        ("c", tokenize("Chocolate cake requires cocoa and flour.")),
    ]
    index = BM25Index(docs)
    ranked = index.rank(tokenize("ERR_CONNECTION_REFUSED"), top_k=3)
    assert ranked[0][0] == "b"


def test_rare_term_ranks_first() -> None:
    docs = [
        ("a", tokenize("The transformer architecture uses self-attention.")),
        ("b", tokenize("Experiment identifier XRQ-917-BETA was recorded.")),
        ("c", tokenize("Astronomers study stellar formation.")),
    ]
    index = BM25Index(docs)
    ranked = index.rank(tokenize("XRQ-917-BETA"), top_k=3)
    assert ranked[0][0] == "b"


def test_ranking_is_deterministic() -> None:
    docs = [
        ("z", tokenize("alpha beta")),
        ("a", tokenize("alpha beta")),
    ]
    index = BM25Index(docs)
    first = index.rank(tokenize("alpha"), top_k=2)
    second = index.rank(tokenize("alpha"), top_k=2)
    assert first == second
    assert first[0][0] < first[1][0] or first[0][1] != first[1][1]


def test_zero_overlap_is_omitted() -> None:
    docs = [("a", tokenize("transformer attention")), ("b", tokenize("chocolate cake"))]
    ranked = BM25Index(docs).rank(tokenize("ERR_CONNECTION_REFUSED"), top_k=5)
    assert ranked == []
