from pathlib import Path

from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.core.errors import GenerationError
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.generation.models import ValidationStatus
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.reranking.overlap import OverlapReranker
from research_assistant.retrieval.filters import RetrievalFilter
from tests.conftest import FIXTURES

LEXICAL = FIXTURES / "lexical"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "docs.db",
        log_level="WARNING",
        max_file_bytes=50 * 1024 * 1024,
        embedding_model_name="hashing",
        embedding_device="cpu",
        vector_index_path=tmp_path / "qdrant",
        default_top_k=5,
        dense_candidate_k=10,
        lexical_candidate_k=10,
        reranker_model_name="overlap",
        rerank_candidate_k=8,
        rerank_top_k=5,
        max_context_tokens=256,
        rrf_k=60,
        llm_provider="scripted",
        llm_model_name="scripted.v1",
    )


def _chunking() -> ChunkingConfig:
    return ChunkingConfig(
        strategy="structure",
        target_chars=400,
        max_chars=600,
        min_chars=10,
        overlap_chars=0,
    )


def _index_corpus(app):
    cfg = _chunking()
    chunker_id = None
    for path in sorted(LEXICAL.glob("*.md")):
        ingested = app.ingest.ingest(path)
        assert ingested.document is not None
        chunked = app.chunking.chunk_document(ingested.document.document_id, cfg)
        chunker_id = chunked.chunker_id
        app.indexing.index_document(ingested.document.document_id, chunker_id)
    assert chunker_id is not None
    return chunker_id


def test_rag_end_to_end_with_scripted_llm(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        '{"answer": "Connection refused is a socket error [S1].", "insufficient_evidence": false}'
    )
    app = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
    )
    chunker_id = _index_corpus(app)
    result = app.rag.answer("ERR_CONNECTION_REFUSED", chunker_id=chunker_id)
    assert result.evidence.context.items
    assert result.answer.ok
    cited = {item.source.chunk_id for item in result.answer.citations}
    available = {item.source.chunk_id for item in result.evidence.context.items}
    assert cited <= available
    assert result.answer.citations[0].citation_id == "S1"
    assert llm.requests
    assert result.answer.diagnostics.empty_context_short_circuit is False


def test_rag_filter_survives_to_citations(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        '{"answer": "Transformers use self-attention [S1].", "insufficient_evidence": false}'
    )
    app = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
    )
    chunker_id = _index_corpus(app)
    ingested = app.ingest.ingest(LEXICAL / "transformer.md")
    assert ingested.document is not None
    allowed = ingested.document.document_id
    result = app.rag.answer(
        "transformer architecture",
        chunker_id=chunker_id,
        filters=RetrievalFilter(document_ids=(allowed,)),
    )
    assert all(hit.document_id == allowed for hit in result.evidence.search.hits)
    assert all(item.source.document_id == allowed for item in result.evidence.context.items)
    assert all(item.source.document_id == allowed for item in result.answer.citations)


def test_invalid_citation_cannot_become_a_source(tmp_path: Path) -> None:
    llm = ScriptedLLM('{"answer": "Invented support [S99].", "insufficient_evidence": false}')
    app = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
    )
    chunker_id = _index_corpus(app)
    result = app.rag.answer("ERR_CONNECTION_REFUSED", chunker_id=chunker_id)
    assert result.answer.validation_status is ValidationStatus.INVALID_CITATION
    assert result.answer.citations == ()
    assert "S99" in result.answer.invalid_citation_ids


def test_conflicting_sources_keep_both_markers() -> None:
    from research_assistant.context.builder import CitationAwareContextBuilder
    from research_assistant.generation.service import GroundedGenerationService
    from research_assistant.retrieval.models import RetrievalHit

    def hit(**kwargs):
        base = dict(
            rank=1,
            score=0.2,
            retriever="hybrid",
            page_start=None,
            page_end=None,
            section_path=(),
            chunker_id="c",
            index_id="i",
            embedding_model_id="e",
        )
        base.update(kwargs)
        return RetrievalHit(**base)

    settings = Settings(
        database_path="unused.db",
        log_level="WARNING",
        max_file_bytes=10,
        reranker_model_name="overlap",
        llm_provider="scripted",
    )
    bundle = CitationAwareContextBuilder(settings).build(
        [
            hit(
                chunk_id="a",
                document_id="d1",
                filename="a.md",
                content_hash="a",
                text="The launch date is 1969.",
            ),
            hit(
                chunk_id="b",
                document_id="d2",
                filename="b.md",
                content_hash="b",
                text="The launch date is 1972.",
            ),
        ]
    )
    llm = ScriptedLLM(
        '{"answer": "Sources disagree: 1969 [S1] versus 1972 [S2].", "insufficient_evidence": false}'
    )
    result = GroundedGenerationService(settings, llm=llm).generate("When was launch?", bundle)
    assert result.ok
    assert "[S1]" in result.answer_text and "[S2]" in result.answer_text
    assert {item.citation_id for item in result.citations} == {"S1", "S2"}


def test_empty_evidence_does_not_call_llm(tmp_path: Path) -> None:
    def boom(_request):
        raise GenerationError("should not call", code="provider_unavailable")

    app = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=ScriptedLLM(boom),
    )
    from research_assistant.context.models import ContextBundle, ContextDiagnostics

    empty = ContextBundle(
        query="q",
        items=(),
        rendered_text="",
        diagnostics=ContextDiagnostics(
            input_count=0,
            selected_count=0,
            skipped_count=0,
            duplicate_count=0,
            redundant_count=0,
            truncated_count=0,
            skipped_budget_count=0,
            max_context_tokens=256,
            estimated_tokens=0,
            accounting="approx_char/4",
            citation_ids=(),
            source_document_count=0,
            skipped_chunk_ids=(),
        ),
    )
    result = app.generation.generate("q", empty)
    assert result.diagnostics.empty_context_short_circuit is True
    assert result.insufficient_evidence is True
