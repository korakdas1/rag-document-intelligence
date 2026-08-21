from pathlib import Path

from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.conversation.models import ConversationTurn
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.reranking.overlap import OverlapReranker

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "conversation_followup"


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


def test_followup_sequence_keeps_subjects_and_document_evidence(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        (
            '{"answer": "Mira Solen and Julian Pike [S1].", "insufficient_evidence": false}',
            '{"answer": "Yes. They later marry [S1].", "insufficient_evidence": false}',
            '{"answer": "Yes. Mira Solen and Julian Pike marry [S1].", "insufficient_evidence": false}',
            '{"answer": "The ending is presented positively [S1].", "insufficient_evidence": false}',
            '{"answer": "They marry two years later [S1].", "insufficient_evidence": false}',
            '{"answer": "They marry two years later [S1].", "insufficient_evidence": false}',
            '{"answer": "The documents do not say they delayed the vote.", "insufficient_evidence": true}',
        )
    )
    app = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
    )
    ingested = app.ingest.ingest(FIXTURE / "mira_and_julian.md")
    assert ingested.document is not None
    chunked = app.chunking.chunk_document(ingested.document.document_id, _chunking())
    app.indexing.index_document(ingested.document.document_id, chunked.chunker_id)
    chunker_id = chunked.chunker_id

    first = app.rag.answer("Whose relationship is this?", chunker_id=chunker_id)
    history = [
        ConversationTurn(
            question="Whose relationship is this?",
            answer=first.answer.answer_text,
            grounding_status="grounded",
            sequence=1,
        )
    ]
    turns = [
        "Do they get together?",
        "Do they marry?",
        "Is it a happy ending?",
        "When do they marry?",
    ]
    location_tokens = ("northhaven", "reach", "bramble", "cedar", "quay", "ostern", "grell")
    for question in turns:
        result = app.rag.answer(
            question,
            chunker_id=chunker_id,
            conversation=tuple(history),
        )
        query = result.query.lower()
        assert "mira solen" in query
        assert "julian pike" in query
        assert all(token not in query for token in location_tokens)
        evidence = result.evidence.context.rendered_text.lower()
        assert "mira solen" in evidence or "julian pike" in evidence
        assert result.answer.insufficient_evidence is False
        assert result.answer.ok
        assert result.answer.citations
        history.append(
            ConversationTurn(
                question=question,
                answer=result.answer.answer_text,
                grounding_status="grounded",
                sequence=len(history) + 1,
            )
        )
    when = app.rag.answer(
        "When?",
        chunker_id=chunker_id,
        conversation=(
            ConversationTurn(
                question="Do Mira Solen and Julian Pike marry?",
                answer=(
                    "Mira and Julian were married in the coastal village of "
                    "Northhaven Reach. [S1]"
                ),
                sequence=1,
            ),
        ),
    )
    query = when.query.lower()
    assert "mira solen" in query
    assert "julian pike" in query
    assert "northhaven" not in query
    assert "reach" not in query
    assert when.original_query == "When?"
    unsupported = app.rag.answer(
        "Did they delay the bridge vote?",
        chunker_id=chunker_id,
        conversation=tuple(history),
    )
    assert "mira solen" in unsupported.query.lower()
    assert "julian pike" in unsupported.query.lower()
    assert unsupported.original_query == "Did they delay the bridge vote?"
    assert unsupported.answer.insufficient_evidence is True
    question_block = llm.requests[-1].messages[1].content
    evidence_block = llm.requests[-1].messages[2].content
    assert "Mira Solen" in question_block
    assert "Did they delay the bridge vote?" not in evidence_block
    assert "They marry two years later" not in evidence_block
