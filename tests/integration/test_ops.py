from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from research_assistant.api.app import create_api
from research_assistant.api.upload import sanitize_filename, unique_destination, validate_upload_content_type
from research_assistant.app import create_application
from research_assistant.core.errors import (
    ConfigurationError,
    DatabaseError,
    FileValidationError,
    GenerationError,
    UnsupportedFileTypeError,
    VectorStoreError,
)
from research_assistant.core.settings import Settings, load_settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.reranking.overlap import OverlapReranker
from research_assistant.storage.sqlite import SqliteDocumentStore
from tests.conftest import FIXTURES

LEXICAL = FIXTURES / "lexical"


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values = dict(
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
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _client(tmp_path: Path, llm: ScriptedLLM | None = None, **overrides: object) -> TestClient:
    application = create_application(
        _settings(tmp_path, **overrides),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm
        or ScriptedLLM(
            '{"answer": "Connection refused is a socket error [S1].", '
            '"insufficient_evidence": false}'
        ),
    )
    return TestClient(create_api(application))


def test_request_id_accepts_safe_incoming_and_rejects_junk(tmp_path: Path) -> None:
    client = _client(tmp_path)
    ok = client.get("/api/health", headers={"X-Request-Id": "req_12345678"})
    assert ok.headers["x-request-id"] == "req_12345678"
    junk = client.get("/api/health", headers={"X-Request-Id": "spaces and newlines\nAuthorization: secret"})
    assert junk.headers["x-request-id"] != "spaces and newlines\nAuthorization: secret"
    assert len(junk.headers["x-request-id"]) >= 8


def test_unhandled_exception_does_not_leak_internals(tmp_path: Path) -> None:
    application = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=ScriptedLLM('{"answer": "ok [S1].", "insufficient_evidence": false}'),
    )
    client = TestClient(create_api(application), raise_server_exceptions=False)

    def boom() -> object:
        raise RuntimeError("secret /tmp/hidden.db SELECT * FROM documents")

    client.app.state.library.list_documents = boom  # type: ignore[method-assign]
    response = client.get("/api/documents")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["request_id"]
    assert "Traceback" not in response.text
    assert "/tmp/hidden" not in response.text
    assert "SELECT" not in response.text


def test_database_locked_maps_to_busy(tmp_path: Path) -> None:
    import sqlite3

    application = create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=ScriptedLLM('{"answer": "ok [S1].", "insufficient_evidence": false}'),
    )
    client = TestClient(create_api(application), raise_server_exceptions=False)

    def locked() -> object:
        raise sqlite3.OperationalError("database is locked")

    client.app.state.library.list_documents = locked  # type: ignore[method-assign]
    response = client.get("/api/documents")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_busy"
    assert "OperationalError" not in response.text


def test_corrupt_sqlite_is_not_recreated(tmp_path: Path) -> None:
    path = tmp_path / "broken.db"
    original = b"this is not a sqlite database" * 40
    path.write_bytes(original)
    with pytest.raises(DatabaseError) as exc:
        SqliteDocumentStore(path)
    assert exc.value.code == "database_corrupt"
    assert path.read_bytes() == original


def test_qdrant_unavailable_on_ready_is_degraded(tmp_path: Path) -> None:
    client = _client(tmp_path)

    class Dead:
        def collection_exists(self, _name: str) -> bool:
            raise VectorStoreError("down", code="vector_store_unavailable")

    client.app.state.application.indexing._vectors = Dead()  # type: ignore[attr-defined]
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["vector_store"]["status"] == "unavailable"
    assert body["database"]["status"] == "ok"
    listed = client.get("/api/documents")
    assert listed.status_code == 200


def test_provider_timeout_is_504(tmp_path: Path) -> None:
    llm = ScriptedLLM(error=GenerationError("timed out", code="timeout"))
    client = _client(tmp_path, llm=llm)
    path = LEXICAL / "error_code.md"
    uploaded = client.post(
        "/api/documents",
        files={"file": (path.name, path.read_bytes(), "text/markdown")},
    )
    assert uploaded.status_code == 200
    response = client.post("/api/ask", json={"question": "ERR_CONNECTION_REFUSED"})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "timeout"


def test_question_too_long_rejected_before_ask(tmp_path: Path) -> None:
    client = _client(tmp_path, max_question_chars=8)
    path = LEXICAL / "error_code.md"
    client.post(
        "/api/documents",
        files={"file": (path.name, path.read_bytes(), "text/markdown")},
    )
    response = client.post("/api/ask", json={"question": "this is clearly too long"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "question_too_long"


def test_oversized_upload_is_413(tmp_path: Path) -> None:
    client = _client(tmp_path, max_file_bytes=16)
    response = client.post(
        "/api/documents",
        files={"file": ("note.md", b"0123456789abcdef0123", "text/markdown")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "too_large"


def test_malformed_pdf_does_not_become_ready(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/api/documents",
        files={"file": ("broken.pdf", b"not-a-pdf-file", "application/pdf")},
    )
    assert response.status_code in {400, 422}
    assert response.json()["error"]["code"] in {"parse_error", "not_a_pdf"}
    assert "/tmp" not in response.text
    listed = client.get("/api/documents").json()["documents"]
    assert listed == []


def test_content_type_mismatch_is_415() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload_content_type("notes.md", "image/png")
    validate_upload_content_type("notes.md", "application/octet-stream")
    validate_upload_content_type("paper.pdf", "application/pdf")


def test_unique_destination_blocks_traversal(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError):
        unique_destination(tmp_path, "../passwd.md")
    with pytest.raises(FileValidationError):
        unique_destination(tmp_path, "/tmp/notes.md")
    assert sanitize_filename("../../etc/passwd.md") == "passwd.md"
    assert sanitize_filename("/etc/notes.txt") == "notes.txt"


def test_cors_allows_configured_localhost_origin(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get(
        "/api/health",
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_load_settings_rejects_invalid_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEARCH_ASSISTANT_DATABASE_PATH", str(tmp_path / "ok.db"))
    monkeypatch.setenv("RESEARCH_ASSISTANT_LLM_TIMEOUT_SECONDS", "-1")
    with pytest.raises(ConfigurationError, match="TIMEOUT"):
        load_settings()
    monkeypatch.delenv("RESEARCH_ASSISTANT_LLM_TIMEOUT_SECONDS")
    monkeypatch.setenv("RESEARCH_ASSISTANT_CONVERSATION_WINDOW", "0")
    with pytest.raises(ConfigurationError, match="CONVERSATION_WINDOW"):
        load_settings()
    monkeypatch.delenv("RESEARCH_ASSISTANT_CONVERSATION_WINDOW")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RESEARCH_ASSISTANT_CORS_ORIGINS", "*")
    with pytest.raises(ConfigurationError, match="CORS"):
        load_settings()
    monkeypatch.setenv("RESEARCH_ASSISTANT_CORS_ORIGINS", "http://127.0.0.1:5173")
    monkeypatch.setenv("API_PORT", "70000")
    with pytest.raises(ConfigurationError, match="API_PORT"):
        load_settings()
    monkeypatch.setenv("API_PORT", "8000")
    monkeypatch.setenv("RESEARCH_ASSISTANT_LLM_MODEL", "")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(ConfigurationError, match="LLM model"):
        load_settings()
