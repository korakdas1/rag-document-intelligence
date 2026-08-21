from pathlib import Path

from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.reranking.scripted import ScriptedReranker
from research_assistant.reranking.service import RerankingService
from research_assistant.retrieval.trace import RetrievalTracer

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "retrieval_trace"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "trace.db",
        log_level="WARNING",
        max_file_bytes=1024 * 1024,
        embedding_model_name="hashing",
        embedding_device="cpu",
        vector_index_path=tmp_path / "qdrant",
        dense_candidate_k=10,
        lexical_candidate_k=10,
        reranker_model_name="scripted",
        rerank_candidate_k=10,
        rerank_top_k=2,
        max_context_tokens=200,
    )


def _prepare(tmp_path: Path):
    settings = _settings(tmp_path)
    app = create_application(
        settings,
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=ScriptedReranker(),
    )
    config = ChunkingConfig(
        strategy="structure",
        target_chars=400,
        max_chars=600,
        min_chars=10,
        overlap_chars=0,
    )
    chunker_id = config.chunker_id
    for path in sorted(FIXTURE.glob("*.md")):
        ingested = app.ingest.ingest(path)
        assert ingested.document is not None
        chunked = app.chunking.chunk_document(
            ingested.document.document_id,
            config,
        )
        assert chunked.ok
        indexed = app.indexing.index_document(
            ingested.document.document_id,
            chunker_id,
        )
        assert indexed.ok
    gold = next(
        chunk
        for chunk in app.store.list_chunks_for_chunker(chunker_id)
        if "married at the riverside hall" in chunk.text
    )
    return app, settings, gold


def _tracer(app, settings, scores):
    return RetrievalTracer(
        dense=app.search,
        lexical=app.lexical,
        hybrid=app.hybrid,
        reranker=RerankingService(
            settings,
            reranker=ScriptedReranker(scores),
        ),
        context=app.context,
        settings=settings,
    )


def test_gold_chunk_survives_all_stages_when_reranker_keeps_it(
    tmp_path: Path,
) -> None:
    app, settings, gold = _prepare(tmp_path)
    trace = _tracer(app, settings, {gold.chunk_id: 10.0}).trace(
        "Do Asha Vale and Rowan Pike marry and have a happy ending?",
        target_chunk_id=gold.chunk_id,
        chunker_id=gold.chunker_id,
        rerank_enabled=True,
    )
    assert trace.dense_rank is not None
    assert trace.lexical_rank is not None
    assert trace.hybrid_rank is not None
    assert trace.rerank_rank == 1
    assert trace.selected_in_context is True
    assert trace.context_position == 1
    assert trace.context_tokens_used_before == 0
    assert trace.dropped_reason is None


def test_trace_identifies_rerank_top_k_loss(tmp_path: Path) -> None:
    app, settings, gold = _prepare(tmp_path)
    candidates = app.hybrid.search(
        "Do Asha Vale and Rowan Pike marry?",
        chunker_id=gold.chunker_id,
        top_k=10,
    ).hits
    distractors = [
        item.chunk_id for item in candidates if item.chunk_id != gold.chunk_id
    ]
    assert len(distractors) >= 2
    scores = {
        distractors[0]: 10.0,
        distractors[1]: 9.0,
        gold.chunk_id: -1.0,
    }
    trace = _tracer(app, settings, scores).trace(
        "Do Asha Vale and Rowan Pike marry?",
        target_chunk_id=gold.chunk_id,
        chunker_id=gold.chunker_id,
        rerank_enabled=True,
    )
    assert trace.hybrid_rank is not None
    assert trace.rerank_rank is not None
    assert trace.rerank_rank > settings.rerank_top_k
    assert trace.selected_in_context is False
    assert trace.dropped_reason == "outside_rerank_top_k"
