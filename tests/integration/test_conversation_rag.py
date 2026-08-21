from pathlib import Path

from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.conversation.models import ConversationTurn
from research_assistant.conversation.scripted import ScriptedQueryResolver
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.reranking.overlap import OverlapReranker
from research_assistant.retrieval.filters import RetrievalFilter

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "evaluation" / "corpus" / "followup"
LEXICAL = Path(__file__).resolve().parents[1] / "fixtures" / "lexical"


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
        conversation_window=4,
    )


def _chunking() -> ChunkingConfig:
    return ChunkingConfig(
        strategy="structure",
        target_chars=400,
        max_chars=600,
        min_chars=10,
        overlap_chars=0,
    )


def _index(app, path: Path) -> tuple[str, str]:
    ingested = app.ingest.ingest(path)
    assert ingested.document is not None
    chunked = app.chunking.chunk_document(ingested.document.document_id, _chunking())
    app.indexing.index_document(ingested.document.document_id, chunked.chunker_id)
    return ingested.document.document_id, chunked.chunker_id


def test_followup_uses_standalone_query_and_document_evidence(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        (
            '{"answer": "Willow Reed and Ash Calder [S1].", "insufficient_evidence": false}',
            '{"answer": "They marry later [S1].", "insufficient_evidence": false}',
        )
    )
    app = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
    )
    _doc_id, chunker_id = _index(app, CORPUS / "willow_and_ash.md")
    first = app.rag.answer("Who are the couple?", chunker_id=chunker_id)
    history = (
        ConversationTurn(
            question="Who are the couple?",
            answer=first.answer.answer_text,
            grounding_status="grounded",
            sequence=1,
        ),
    )
    second = app.rag.answer("Do they marry?", chunker_id=chunker_id, conversation=history)
    assert "Willow Reed" in second.query
    assert "Ash Calder" in second.query
    assert second.original_query == "Do they marry?"
    assert second.resolution is not None
    assert second.resolution.rewrite_applied is True
    evidence_text = second.evidence.context.rendered_text
    assert "Who are the couple?" not in evidence_text
    question_block = llm.requests[-1].messages[1].content
    evidence_block = llm.requests[-1].messages[2].content
    assert "Willow Reed" in question_block
    assert "Ash Calder" in question_block
    assert "Who are the couple?" not in evidence_block


def test_wrong_assistant_answer_is_not_added_to_context(tmp_path: Path) -> None:
    sentinel = "UNIQUE_WRONG_ANSWER_SENTINEL_NO_MARRIAGE"
    llm = ScriptedLLM(
        '{"answer": "Willow Reed and Ash Calder marry in the village hall [S1].", '
        '"insufficient_evidence": false}'
    )
    app = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
    )
    _doc_id, chunker_id = _index(app, CORPUS / "willow_and_ash.md")
    history = (
        ConversationTurn(
            question="Whose love story is this?",
            answer="Willow Reed and Ash Calder.",
            sequence=1,
        ),
        ConversationTurn(
            question="Do they get together?",
            answer=sentinel,
            sequence=2,
        ),
    )
    result = app.rag.answer(
        "But the document says they marry. Are you sure?",
        chunker_id=chunker_id,
        conversation=history,
    )
    assert sentinel not in result.evidence.context.rendered_text
    assert sentinel not in result.query
    assert "Willow Reed" in result.query
    assert "Ash Calder" in result.query


def test_document_filter_survives_followup(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        '{"answer": "Willow Reed and Ash Calder [S1].", "insufficient_evidence": false}'
    )
    app = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
    )
    love_id, chunker_id = _index(app, CORPUS / "willow_and_ash.md")
    _index(app, LEXICAL / "error_code.md")
    history = (
        ConversationTurn(
            question="Whose love story is this?",
            answer="Willow Reed and Ash Calder.",
            sequence=1,
        ),
    )
    result = app.rag.answer(
        "Do they marry?",
        chunker_id=chunker_id,
        conversation=history,
        filters=RetrievalFilter(document_ids=(love_id,)),
    )
    assert all(hit.document_id == love_id for hit in result.evidence.search.hits)
    assert all(item.source.document_id == love_id for item in result.evidence.context.items)


def test_scripted_resolver_query_is_what_retrieval_sees(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        '{"answer": "Willow Reed and Ash Calder marry [S1].", "insufficient_evidence": false}'
    )
    resolver = ScriptedQueryResolver(
        "Do Willow Reed and Ash Calder marry in the indexed story?",
        followup_detected=True,
    )
    app = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
        resolver=resolver,
    )
    _doc_id, chunker_id = _index(app, CORPUS / "willow_and_ash.md")
    result = app.rag.answer(
        "Do they marry?",
        chunker_id=chunker_id,
        conversation=(ConversationTurn(question="Who?", answer="Willow Reed and Ash Calder."),),
    )
    assert result.query == "Do Willow Reed and Ash Calder marry in the indexed story?"
    assert result.evidence.context.query == result.query
    assert resolver.questions == ["Do they marry?"]
    assert "Do they marry? Whose love story" not in result.query


def test_pronoun_without_history_does_not_guess_from_evidence(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        '{"answer": "The system launched in March [S1].", "insufficient_evidence": false}'
    )
    app = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
    )
    _doc_id, chunker_id = _index(app, CORPUS / "willow_and_ash.md")
    result = app.rag.answer("When did it launch?", chunker_id=chunker_id)
    assert result.resolution is not None
    assert result.resolution.diagnostics.method == "unresolved_no_history"
    assert result.answer.insufficient_evidence is True
    assert result.answer.diagnostics.unresolved_referent_short_circuit is True
    assert llm.requests == []
    assert "March" not in result.answer.answer_text
