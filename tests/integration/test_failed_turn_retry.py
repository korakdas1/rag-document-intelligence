"""Failed-turn retry identity: persist, recover, replace in place. No RAG protocol changes."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from research_assistant.api.app import create_api
from research_assistant.app import create_application
from research_assistant.core.errors import GenerationError
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.generation.models import LLMRequest, LLMResponse
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.reranking.overlap import OverlapReranker
from research_assistant.storage.sqlite import SqliteDocumentStore
from tests.conftest import FIXTURES

LEXICAL = FIXTURES / "lexical"
QUESTION = "Where were Harry and Hermione married?"


class _FailThenSucceedLLM:
    """Raise provider_unavailable N times, then delegate. Test double only."""

    def __init__(self, inner: ScriptedLLM, *, failures: int = 1) -> None:
        self._inner = inner
        self._failures = failures
        self.requests: list[LLMRequest] = []

    @property
    def identity(self):
        return self._inner.identity

    def recover(self) -> None:
        self._failures = 0

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self._failures > 0:
            self._failures -= 1
            raise GenerationError(
                "LLM provider unavailable: [Errno 111] Connection refused",
                code="provider_unavailable",
            )
        return self._inner.generate(request)


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
        conversation_window=4,
    )


def _application(tmp_path: Path, llm):
    return create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
    )


def _client(tmp_path: Path, llm) -> tuple[TestClient, object]:
    application = _application(tmp_path, llm)
    return TestClient(create_api(application)), application


def _upload(client: TestClient) -> dict:
    path = LEXICAL / "error_code.md"
    response = client.post(
        "/api/documents",
        files={"file": ("error_code.md", path.read_bytes(), "text/markdown")},
    )
    assert response.status_code == 200, response.text
    return response.json()["document"]


def _sql_turns(db_path: Path, session_id: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT turn_id, sequence, question, answer, grounding_status, error_message,
               sources_json, citations_json
        FROM conversation_turns
        WHERE session_id = ?
        ORDER BY sequence ASC, turn_id ASC
        """,
        (session_id,),
    ).fetchall()
    conn.close()
    return rows


def _restart(tmp_path: Path, db_path: Path, llm) -> tuple[TestClient, object]:
    restarted = create_application(
        _settings(tmp_path),
        store=SqliteDocumentStore(db_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm,
    )
    return TestClient(create_api(restarted)), restarted


def _succeeding_llm() -> ScriptedLLM:
    return ScriptedLLM(
        '{"answer": "The documents do not describe that wedding [S1].", '
        '"insufficient_evidence": false}'
    )


def test_provider_failure_persists_retryable_turn(tmp_path: Path) -> None:
    llm = _FailThenSucceedLLM(_succeeding_llm(), failures=1)
    client, application = _client(tmp_path, llm)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    failed = client.post(
        "/api/ask",
        json={"question": QUESTION, "session_id": session_id},
    )
    assert failed.status_code == 503
    error = failed.json()["error"]
    assert error["code"] == "provider_unavailable"
    assert "Turn not found" not in error["message"]
    assert error["turn_id"]
    assert error["session_id"] == session_id
    stored = application.store.get_turn(error["turn_id"])
    assert stored is not None
    assert stored.session_id == session_id
    assert stored.question == QUESTION
    assert stored.grounding_status == "error"
    assert stored.error_message
    loaded = client.get(f"/api/sessions/{session_id}").json()
    assert loaded["turn_count"] == 1
    assert loaded["turns"][0]["turn_id"] == error["turn_id"]
    assert loaded["turns"][0]["error_message"]
    assert loaded["turns"][0]["grounding_status"] == "error"


def test_retry_after_provider_recovery_updates_same_turn(tmp_path: Path) -> None:
    llm = _FailThenSucceedLLM(_succeeding_llm(), failures=1)
    client, application = _client(tmp_path, llm)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    failed = client.post(
        "/api/ask",
        json={"question": QUESTION, "session_id": session_id},
    )
    turn_id = failed.json()["error"]["turn_id"]
    llm.recover()
    retried = client.post(
        "/api/ask",
        json={
            "question": QUESTION,
            "session_id": session_id,
            "replace_turn_id": turn_id,
        },
    )
    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["turn_id"] == turn_id
    assert body["session_id"] == session_id
    assert body["question"] == QUESTION
    assert body["grounding_status"] != "insufficient_evidence"
    assert "Turn not found" not in (body.get("answer") or "")
    assert body["diagnostics"]["original_question"] == QUESTION
    rows = application.store.list_turns(session_id)
    assert len(rows) == 1
    assert rows[0].turn_id == turn_id
    assert rows[0].question == QUESTION
    assert rows[0].grounding_status != "error"
    assert rows[0].error_message is None


def test_retry_uses_original_question_in_same_session(tmp_path: Path) -> None:
    llm = _FailThenSucceedLLM(_succeeding_llm(), failures=1)
    client, _application = _client(tmp_path, llm)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    turn_id = client.post(
        "/api/ask",
        json={"question": QUESTION, "session_id": session_id},
    ).json()["error"]["turn_id"]
    other = client.post("/api/sessions", json={}).json()["session_id"]
    retried = client.post(
        "/api/ask",
        json={
            "question": QUESTION,
            "session_id": session_id,
            "replace_turn_id": turn_id,
        },
    )
    assert retried.status_code == 200
    assert retried.json()["session_id"] == session_id
    assert retried.json()["session_id"] != other
    loaded = client.get(f"/api/sessions/{session_id}").json()
    assert loaded["turns"][0]["question"] == QUESTION
    assert client.get(f"/api/sessions/{other}").json()["turn_count"] == 0


def test_failed_turn_survives_backend_restart_and_retry(tmp_path: Path) -> None:
    llm = _FailThenSucceedLLM(_succeeding_llm(), failures=1)
    client, application = _client(tmp_path, llm)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    failed = client.post(
        "/api/ask",
        json={"question": QUESTION, "session_id": session_id},
    )
    turn_id = failed.json()["error"]["turn_id"]
    db_path = application.settings.database_path
    recovered = _FailThenSucceedLLM(_succeeding_llm(), failures=0)
    restarted = create_application(
        _settings(tmp_path),
        store=SqliteDocumentStore(db_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=recovered,
    )
    restored_client = TestClient(create_api(restarted))
    loaded = restored_client.get(f"/api/sessions/{session_id}")
    assert loaded.status_code == 200
    assert loaded.json()["turns"][0]["turn_id"] == turn_id
    assert loaded.json()["turns"][0]["grounding_status"] == "error"
    retried = restored_client.post(
        "/api/ask",
        json={
            "question": QUESTION,
            "session_id": session_id,
            "replace_turn_id": turn_id,
        },
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["turn_id"] == turn_id
    assert retried.json()["session_id"] == session_id


def test_retry_unknown_turn_returns_not_found(tmp_path: Path) -> None:
    client, _application = _client(tmp_path, _succeeding_llm())
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    missing = client.post(
        "/api/ask",
        json={
            "question": QUESTION,
            "session_id": session_id,
            "replace_turn_id": "deadbeefdeadbeefdeadbeefdeadbeef",
        },
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert missing.json()["error"]["message"] == "Turn not found."
    assert client.get(f"/api/sessions/{session_id}").json()["turn_count"] == 0


def test_retry_deleted_session_returns_not_found(tmp_path: Path) -> None:
    llm = _FailThenSucceedLLM(_succeeding_llm(), failures=1)
    client, _application = _client(tmp_path, llm)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    turn_id = client.post(
        "/api/ask",
        json={"question": QUESTION, "session_id": session_id},
    ).json()["error"]["turn_id"]
    assert client.delete(f"/api/sessions/{session_id}").status_code == 200
    retried = client.post(
        "/api/ask",
        json={
            "question": QUESTION,
            "session_id": session_id,
            "replace_turn_id": turn_id,
        },
    )
    assert retried.status_code == 404
    assert retried.json()["error"]["code"] == "not_found"


def test_hyphenated_client_id_is_not_a_persisted_turn(tmp_path: Path) -> None:
    llm = _FailThenSucceedLLM(_succeeding_llm(), failures=1)
    client, application = _client(tmp_path, llm)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    failed = client.post(
        "/api/ask",
        json={"question": QUESTION, "session_id": session_id},
    )
    persisted = failed.json()["error"]["turn_id"]
    orphan = client.post(
        "/api/ask",
        json={
            "question": QUESTION,
            "session_id": session_id,
            "replace_turn_id": "550e8400-e29b-41d4-a716-446655440000",
        },
    )
    assert orphan.status_code == 404
    assert orphan.json()["error"]["message"] == "Turn not found."
    assert application.store.get_turn(persisted) is not None


def test_successful_retry_survives_session_reload_and_backend_restart(tmp_path: Path) -> None:
    llm = _FailThenSucceedLLM(_succeeding_llm(), failures=1)
    client, application = _client(tmp_path, llm)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    db_path = application.settings.database_path

    assert _sql_turns(db_path, session_id) == []

    failed = client.post("/api/ask", json={"question": QUESTION, "session_id": session_id})
    assert failed.status_code == 503
    turn_id = failed.json()["error"]["turn_id"]
    before = _sql_turns(db_path, session_id)
    assert len(before) == 1
    assert before[0]["turn_id"] == turn_id
    assert before[0]["sequence"] == 1
    assert before[0]["grounding_status"] == "error"
    assert "Connection refused" in (before[0]["error_message"] or "")
    assert before[0]["answer"] == ""

    retried = client.post(
        "/api/ask",
        json={"question": QUESTION, "session_id": session_id, "replace_turn_id": turn_id},
    )
    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["turn_id"] == turn_id
    assert body["session_id"] == session_id
    assert body["answer"]
    assert body["grounding_status"] != "error"
    assert body["sources"]
    assert body["citations"] or body["grounding_status"] == "unverified"

    after = _sql_turns(db_path, session_id)
    assert len(after) == 1
    assert after[0]["turn_id"] == turn_id
    assert after[0]["sequence"] == 1
    assert after[0]["question"] == QUESTION
    assert after[0]["grounding_status"] != "error"
    assert after[0]["error_message"] is None
    assert after[0]["answer"] == body["answer"]
    assert after[0]["sources_json"] != "[]"

    immediate = client.get(f"/api/sessions/{session_id}").json()
    assert immediate["turn_count"] == 1
    assert immediate["turns"][0]["turn_id"] == turn_id
    assert immediate["turns"][0]["grounding_status"] != "error"
    assert immediate["turns"][0]["error_message"] in {None, ""}
    assert immediate["turns"][0]["answer"] == body["answer"]
    assert immediate["turns"][0]["sources"]

    renamed = client.patch(f"/api/sessions/{session_id}", json={"title": "Harry notes"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Harry notes"

    application.store.close()
    restored_client, restarted = _restart(tmp_path, db_path, _succeeding_llm())
    loaded = restored_client.get(f"/api/sessions/{session_id}")
    assert loaded.status_code == 200
    restored = loaded.json()
    assert restored["title"] == "Harry notes"
    assert restored["turn_count"] == 1
    turn = restored["turns"][0]
    assert turn["turn_id"] == turn_id
    assert turn["sequence"] == 1
    assert turn["question"] == QUESTION
    assert turn["answer"] == body["answer"]
    assert turn["grounding_status"] != "error"
    assert turn["error_message"] in {None, ""}
    assert "Connection refused" not in (turn["answer"] or "")
    assert "Connection refused" not in (turn["error_message"] or "")
    assert turn["sources"]
    raw = _sql_turns(db_path, session_id)
    assert len(raw) == 1
    assert raw[0]["error_message"] is None
    restarted.store.close()


def test_retry_without_replace_id_replaces_trailing_failed_turn(tmp_path: Path) -> None:
    llm = _FailThenSucceedLLM(_succeeding_llm(), failures=1)
    client, application = _client(tmp_path, llm)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    failed = client.post("/api/ask", json={"question": QUESTION, "session_id": session_id})
    turn_id = failed.json()["error"]["turn_id"]
    retried = client.post("/api/ask", json={"question": QUESTION, "session_id": session_id})
    assert retried.status_code == 200, retried.text
    assert retried.json()["turn_id"] == turn_id
    rows = _sql_turns(application.settings.database_path, session_id)
    assert len(rows) == 1
    assert rows[0]["grounding_status"] != "error"
    assert rows[0]["error_message"] is None


def test_unretried_failed_turn_still_restores_as_failure(tmp_path: Path) -> None:
    llm = _FailThenSucceedLLM(_succeeding_llm(), failures=1)
    client, application = _client(tmp_path, llm)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    failed = client.post("/api/ask", json={"question": QUESTION, "session_id": session_id})
    turn_id = failed.json()["error"]["turn_id"]
    db_path = application.settings.database_path
    application.store.close()
    restored_client, restarted = _restart(tmp_path, db_path, _succeeding_llm())
    loaded = restored_client.get(f"/api/sessions/{session_id}").json()
    assert loaded["turns"][0]["turn_id"] == turn_id
    assert loaded["turns"][0]["grounding_status"] == "error"
    assert loaded["turns"][0]["error_message"]
    restarted.store.close()


def test_delete_session_after_retry_removes_the_turn(tmp_path: Path) -> None:
    llm = _FailThenSucceedLLM(_succeeding_llm(), failures=1)
    client, application = _client(tmp_path, llm)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    turn_id = client.post(
        "/api/ask", json={"question": QUESTION, "session_id": session_id}
    ).json()["error"]["turn_id"]
    retried = client.post(
        "/api/ask",
        json={"question": QUESTION, "session_id": session_id, "replace_turn_id": turn_id},
    )
    assert retried.status_code == 200
    assert client.delete(f"/api/sessions/{session_id}").json()["deleted"] is True
    assert client.get(f"/api/sessions/{session_id}").status_code == 404
    assert _sql_turns(application.settings.database_path, session_id) == []
    assert application.store.get_turn(turn_id) is None


def test_successful_ask_still_persists_one_turn(tmp_path: Path) -> None:
    client, application = _client(tmp_path, _succeeding_llm())
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    asked = client.post(
        "/api/ask",
        json={"question": "What is ERR_CONNECTION_REFUSED?", "session_id": session_id},
    )
    assert asked.status_code == 200, asked.text
    body = asked.json()
    assert body["turn_id"]
    assert body["session_id"] == session_id
    assert body["grounding_status"] != "error"
    assert len(application.store.list_turns(session_id)) == 1
