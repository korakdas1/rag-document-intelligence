from pathlib import Path

from fastapi.testclient import TestClient

from research_assistant.api.app import create_api
from research_assistant.app import create_application
from research_assistant.chunking.config import default_config
from research_assistant.core.errors import GenerationError
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.reranking.overlap import OverlapReranker
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
        upload_dir=tmp_path / "uploads",
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


def _client(tmp_path: Path, llm: ScriptedLLM | None = None) -> TestClient:
    application = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm or ScriptedLLM(
            '{"answer": "Connection refused is a socket error [S1].", '
            '"insufficient_evidence": false}'
        ),
    )
    return TestClient(create_api(application))


def test_health_is_liveness_only(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "research-assistant"
    assert "sqlite" not in body
    assert "llm" not in body
    assert response.headers.get("x-request-id")
    root = client.get("/health")
    assert root.status_code == 200
    assert root.json()["status"] == "ok"


def test_ready_reports_scripted_llm(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "degraded"}
    assert body["database"]["status"] == "ok"
    assert body["llm_provider"]["status"] == "ok"
    assert body["embedding"]["status"] == "configured"
    assert "/" not in body["database"]["detail"]


def test_list_empty_then_upload_and_list(tmp_path: Path) -> None:
    client = _client(tmp_path)
    empty = client.get("/api/documents")
    assert empty.status_code == 200
    assert empty.json()["documents"] == []
    path = LEXICAL / "error_code.md"
    uploaded = client.post(
        "/api/documents",
        files={"file": (path.name, path.read_bytes(), "text/markdown")},
    )
    assert uploaded.status_code == 200, uploaded.text
    doc = uploaded.json()["document"]
    assert doc["filename"] == "error_code.md"
    assert doc["status"] == "ready"
    assert doc["chunk_count"] >= 1
    listed = client.get("/api/documents").json()["documents"]
    assert len(listed) == 1
    assert listed[0]["filename"] == "error_code.md"


def test_upload_rejects_unsupported_and_empty(tmp_path: Path) -> None:
    client = _client(tmp_path)
    bad = client.post(
        "/api/documents",
        files={"file": ("note.html", b"<html></html>", "text/html")},
    )
    assert bad.status_code == 415
    assert bad.json()["error"]["code"] == "unsupported_type"
    empty = client.post(
        "/api/documents",
        files={"file": ("empty.md", b"", "text/markdown")},
    )
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "empty_file"


def test_ask_requires_documents(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post("/api/ask", json={"question": "What is attention?"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_ready_documents"


def test_ask_empty_question(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post("/api/ask", json={"question": "   "})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_query"


def _index_fixture(client: TestClient, name: str) -> str:
    path = LEXICAL / name
    uploaded = client.post(
        "/api/documents",
        files={"file": (path.name, path.read_bytes(), "text/markdown")},
    )
    assert uploaded.status_code == 200, uploaded.text
    return uploaded.json()["document"]["document_id"]


def test_ask_success_maps_citation_to_source(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _index_fixture(client, "error_code.md")
    response = client.post(
        "/api/ask",
        json={"question": "ERR_CONNECTION_REFUSED", "retrieval_mode": "hybrid"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["grounding_status"] == "grounded"
    assert body["validation_status"] == "valid"
    assert body["citations"]
    cited = body["citations"][0]["citation_id"]
    sources = {item["citation_id"]: item for item in body["sources"]}
    assert cited in sources
    assert sources[cited]["text"]
    assert sources[cited]["cited_by_model"] is True
    assert sources[cited]["filename"]
    candidates = body["diagnostics"]["candidates"]
    assert candidates
    assert all("selected_in_context" in item for item in candidates)
    assert any(item["selected_in_context"] for item in candidates)
    selected = next(item for item in candidates if item["selected_in_context"])
    assert selected["context_position"] is not None
    assert "page_start" in selected and "section_path" in selected


def test_insufficient_evidence_is_not_an_http_error(tmp_path: Path) -> None:
    llm = ScriptedLLM('{"answer": "", "insufficient_evidence": true}')
    client = _client(tmp_path, llm=llm)
    _index_fixture(client, "error_code.md")
    response = client.post("/api/ask", json={"question": "What is the capital of Mars?"})
    assert response.status_code == 200
    body = response.json()
    assert body["grounding_status"] == "insufficient_evidence"
    assert body["insufficient_evidence"] is True


def test_missing_citations_stay_unverified(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        '{"answer": "Connection refused means the socket was closed.", '
        '"insufficient_evidence": false}'
    )
    client = _client(tmp_path, llm=llm)
    _index_fixture(client, "error_code.md")
    response = client.post("/api/ask", json={"question": "ERR_CONNECTION_REFUSED"})
    assert response.status_code == 200
    body = response.json()
    assert body["grounding_status"] == "unverified"
    assert body["validation_status"] == "missing_citations"
    assert body["citations"] == []
    assert body["sources"], "retrieved evidence must still be inspectable"


def test_provider_error_is_503(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        error=GenerationError("ollama is down", code="provider_unavailable")
    )
    client = _client(tmp_path, llm=llm)
    _index_fixture(client, "error_code.md")
    response = client.post("/api/ask", json={"question": "ERR_CONNECTION_REFUSED"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert "turn_id" not in response.json()["error"]


def test_document_filter_is_server_side(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        '{"answer": "Transformers use self-attention [S1].", "insufficient_evidence": false}'
    )
    client = _client(tmp_path, llm=llm)
    allowed = _index_fixture(client, "transformer.md")
    _index_fixture(client, "astro.md")
    response = client.post(
        "/api/ask",
        json={
            "question": "transformer architecture",
            "document_ids": [allowed],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert all(item["document_id"] == allowed for item in body["sources"])
    assert all(hit["document_id"] == allowed for hit in body["diagnostics"]["candidates"])


def test_ask_followup_rewrites_and_keeps_filter(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        '{"answer": "Willow Reed and Ash Calder marry later [S1].", '
        '"insufficient_evidence": false}'
    )
    client = _client(tmp_path, llm=llm)
    love = client.post(
        "/api/documents",
        files={
            "file": (
                "willow_and_ash.md",
                (Path(__file__).resolve().parents[2] / "evaluation/corpus/followup/willow_and_ash.md").read_bytes(),
                "text/markdown",
            )
        },
    )
    assert love.status_code == 200, love.text
    allowed = love.json()["document"]["document_id"]
    other = _index_fixture(client, "error_code.md")
    assert other != allowed
    response = client.post(
        "/api/ask",
        json={
            "question": "Do they get together?",
            "document_ids": [allowed],
            "conversation": [
                {
                    "question": "Whose love story is this?",
                    "answer": "Willow Reed and Ash Calder.",
                    "grounding_status": "grounded",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["question"] == "Do they get together?"
    diag = body["diagnostics"]
    assert diag["rewrite_applied"] is True
    assert "Willow Reed" in diag["retrieval_query"]
    assert "Ash Calder" in diag["retrieval_query"]
    assert diag["generation_question"] == diag["retrieval_query"]
    assert diag["generation_question"] != body["question"]
    assert diag["context_citation_ids"]
    assert "parsed_inline_citation_ids" in diag
    assert "validated_citation_ids" in diag
    assert "structured_citation_ids" in diag
    assert "insufficient_evidence" in diag
    assert diag["resolver_id"]
    assert "Willow Reed" in " ".join(diag.get("conversation_subjects") or [])
    assert "Ash Calder" in " ".join(diag.get("conversation_subjects") or [])
    assert all(item["document_id"] == allowed for item in body["sources"])
    assert all(hit["document_id"] == allowed for hit in diag["candidates"])


def test_ask_without_conversation_stays_independent(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _index_fixture(client, "error_code.md")
    response = client.post(
        "/api/ask",
        json={"question": "ERR_CONNECTION_REFUSED"},
    )
    assert response.status_code == 200
    diag = response.json()["diagnostics"]
    assert diag["rewrite_applied"] is False
    assert diag["retrieval_query"] == "ERR_CONNECTION_REFUSED"


def test_default_chunker_matches_library(tmp_path: Path) -> None:
    client = _client(tmp_path)
    listed = client.get("/api/documents")
    assert listed.json()["chunker_id"] == default_config().chunker_id
