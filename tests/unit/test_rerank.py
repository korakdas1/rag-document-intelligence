from research_assistant.core.errors import RerankError
from research_assistant.core.settings import Settings
from research_assistant.reranking.identity import RerankerIdentity
from research_assistant.reranking.overlap import OverlapReranker
from research_assistant.reranking.scripted import ScriptedReranker
from research_assistant.reranking.service import RerankingService
from research_assistant.reranking.truncate import prepare_rerank_pair
from research_assistant.retrieval.models import RetrievalHit


def _hit(**kwargs) -> RetrievalHit:
    values = dict(
        chunk_id="c1",
        document_id="d1",
        rank=1,
        score=0.5,
        retriever="hybrid",
        text="self-attention lets transformers relate distant tokens",
        page_start=4,
        page_end=5,
        section_path=("Architecture", "Self-Attention"),
        chunker_id="chunker.v1",
        index_id="idx",
        embedding_model_id="emb",
        filename="paper.pdf",
        content_hash="abc",
        retrievers=("dense", "lexical"),
        dense_rank=2,
        lexical_rank=3,
        dense_score=0.8,
        lexical_score=4.2,
        fused_score=0.03,
        lexical_index_id="lex",
    )
    values.update(kwargs)
    return RetrievalHit(**values)


def test_reranker_receives_query_and_preserves_identity() -> None:
    hits = [
        _hit(chunk_id="a", rank=1, text="attention mechanism over tokens"),
        _hit(chunk_id="b", rank=2, document_id="d2", text="unrelated astronomy nebula"),
    ]
    result = ScriptedReranker({"b": 9.0, "a": 1.0}).rerank("what is attention", hits, top_k=2)
    assert [hit.chunk_id for hit in result.hits] == ["b", "a"]
    assert result.query == "what is attention"
    first = result.hits[0]
    assert first.chunk_id == "b"
    assert first.document_id == "d2"
    assert first.rank == 2
    assert first.fused_score == 0.03
    assert first.dense_rank == 2
    assert first.lexical_rank == 3
    assert first.filename == "paper.pdf"
    assert first.page_start == 4
    assert first.section_path == ("Architecture", "Self-Attention")
    assert first.content_hash == "abc"
    assert first.chunker_id == "chunker.v1"
    assert first.text == "unrelated astronomy nebula"
    assert first.rerank_score == 9.0
    assert first.rerank_rank == 1
    assert first.reranker_id == result.diagnostics.reranker_id
    assert result.hits[1].rerank_rank == 2


def test_top_k_enforced() -> None:
    hits = [_hit(chunk_id=f"c{i}", rank=i, text=f"token {i}") for i in range(1, 6)]
    scores = {f"c{i}": float(i) for i in range(1, 6)}
    result = ScriptedReranker(scores).rerank("q", hits, top_k=2)
    assert len(result.hits) == 2
    assert result.diagnostics.input_count == 5
    assert result.diagnostics.output_count == 2
    assert result.hits[0].rerank_rank == 1


def test_tie_breaks_by_first_stage_rank_then_chunk_id() -> None:
    hits = [
        _hit(chunk_id="z", rank=3, text="same"),
        _hit(chunk_id="a", rank=2, text="same"),
        _hit(chunk_id="m", rank=2, text="same"),
    ]
    result = ScriptedReranker({"z": 1.0, "a": 1.0, "m": 1.0}).rerank("q", hits, top_k=3)
    assert [hit.chunk_id for hit in result.hits] == ["a", "m", "z"]


def test_empty_candidates_are_valid() -> None:
    result = OverlapReranker().rerank("attention", [], top_k=3)
    assert result.hits == ()
    assert result.diagnostics.input_count == 0
    assert result.diagnostics.enabled is True


def test_empty_query_is_rejected() -> None:
    try:
        OverlapReranker().rerank("  ", [_hit()], top_k=1)
    except RerankError as exc:
        assert exc.code == "empty_query"
    else:
        raise AssertionError("expected empty_query")


def test_invalid_top_k() -> None:
    try:
        OverlapReranker().rerank("query", [_hit()], top_k=0)
    except RerankError as exc:
        assert exc.code == "invalid_top_k"
    else:
        raise AssertionError("expected invalid_top_k")


def test_model_failure_does_not_fallback() -> None:
    class Boom:
        @property
        def identity(self) -> RerankerIdentity:
            return RerankerIdentity(
                provider="boom",
                model_name="boom",
                revision="0",
                max_length=0,
                batch_size=0,
                scoring="none",
            )

        def rerank(self, query, candidates, top_k):
            raise RerankError("weights missing", code="model_unavailable")

    settings = Settings(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
        reranker_model_name="overlap",
        rerank_enabled=True,
    )
    service = RerankingService(settings, reranker=Boom())
    try:
        service.rerank("query", [_hit()], top_k=1)
    except RerankError as exc:
        assert exc.code == "model_unavailable"
    else:
        raise AssertionError("expected model_unavailable")


def test_disabled_rerank_keeps_first_stage_order() -> None:
    settings = Settings(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
        rerank_enabled=False,
        rerank_top_k=2,
    )
    hits = [_hit(chunk_id="a", rank=1), _hit(chunk_id="b", rank=2), _hit(chunk_id="c", rank=3)]
    result = RerankingService(settings, reranker=ScriptedReranker({"c": 99})).rerank(
        "query", hits
    )
    assert [hit.chunk_id for hit in result.hits] == ["a", "b"]
    assert result.hits[0].rerank_score is None
    assert result.diagnostics.enabled is False


def test_long_input_truncation_is_recorded() -> None:
    long_text = "attention " * 400
    result = OverlapReranker(max_length=32).rerank(
        "attention", [_hit(text=long_text)], top_k=1
    )
    assert result.diagnostics.truncated_count == 1
    assert result.hits[0].text == long_text


def test_prepare_pair_preserves_query() -> None:
    query = "what is self-attention"
    passage = "x" * 5000
    out_q, out_p, truncated = prepare_rerank_pair(query, passage, max_length=64)
    assert out_q == query
    assert truncated is True
    assert len(out_p) < len(passage)


def test_reranker_id_is_deterministic_and_query_independent() -> None:
    left = OverlapReranker().identity.reranker_id
    right = OverlapReranker().identity.reranker_id
    assert left == right
    assert "attention" not in left
    payload = OverlapReranker().identity.to_dict()
    assert payload["model_name"] == "overlap.v1"
    assert "query" not in payload


def test_overlap_prefers_relevant_passage() -> None:
    hits = [
        _hit(chunk_id="distractor", rank=1, text="distant galaxies form from collapsing gas"),
        _hit(
            chunk_id="gold",
            rank=2,
            text="Self-attention is the mechanism that lets transformers model relationships between distant tokens.",
        ),
    ]
    result = OverlapReranker().rerank(
        "What mechanism allows transformers to model relationships between distant tokens?",
        hits,
        top_k=2,
    )
    assert result.hits[0].chunk_id == "gold"
    assert result.hits[0].rerank_rank == 1
