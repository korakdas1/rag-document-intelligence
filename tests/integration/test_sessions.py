"""Persistent research sessions: SQLite + API. History is never evidence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from research_assistant.api.app import create_api
from research_assistant.app import create_application
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.generation.scripted import ScriptedLLM
from research_assistant.reranking.overlap import OverlapReranker
from research_assistant.storage.sqlite import SCHEMA_VERSION, SqliteDocumentStore
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
        conversation_window=4,
    )


def _application(tmp_path: Path, llm: ScriptedLLM | None = None):
    return create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=llm
        or ScriptedLLM(
            '{"answer": "Connection refused is a socket error [S1].", '
            '"insufficient_evidence": false}'
        ),
    )


def _client(tmp_path: Path, llm: ScriptedLLM | None = None) -> tuple[TestClient, object]:
    application = _application(tmp_path, llm)
    return TestClient(create_api(application)), application


def _upload(client: TestClient, name: str = "error_code.md") -> dict:
    path = LEXICAL / name
    response = client.post(
        "/api/documents",
        files={"file": (name, path.read_bytes(), "text/markdown")},
    )
    assert response.status_code == 200, response.text
    return response.json()["document"]


def test_create_list_rename_delete_session(tmp_path: Path) -> None:
    client, application = _client(tmp_path)
    created = client.post("/api/sessions", json={})
    assert created.status_code == 200, created.text
    session = created.json()
    assert session["title"] == "New research"
    assert session["turn_count"] == 0
    session_id = session["session_id"]
    listed = client.get("/api/sessions").json()["sessions"]
    assert listed[0]["session_id"] == session_id
    renamed = client.patch(f"/api/sessions/{session_id}", json={"title": "  Launch notes  "})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Launch notes"
    empty = client.patch(f"/api/sessions/{session_id}", json={"title": "   "})
    assert empty.status_code == 400
    deleted = client.delete(f"/api/sessions/{session_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(f"/api/sessions/{session_id}").status_code == 404
    retry = client.delete(f"/api/sessions/{session_id}")
    assert retry.json()["already_absent"] is True
    assert application.store.count_documents() == 0


def test_persist_turn_reload_and_restart(tmp_path: Path) -> None:
    client, application = _client(tmp_path)
    _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    asked = client.post(
        "/api/ask",
        json={"question": "What is ERR_CONNECTION_REFUSED?", "session_id": session_id},
    )
    assert asked.status_code == 200, asked.text
    body = asked.json()
    assert body["session_id"] == session_id
    assert body["turn_id"]
    loaded = client.get(f"/api/sessions/{session_id}").json()
    assert loaded["turn_count"] == 1
    assert loaded["title"] == "What is ERR_CONNECTION_REFUSED?"
    turn = loaded["turns"][0]
    assert "Connection refused" in turn["answer"]
    assert turn["sources"]
    db_path = application.settings.database_path
    restarted = create_application(
        _settings(tmp_path),
        store=SqliteDocumentStore(db_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=ScriptedLLM('{"answer": "ok [S1].", "insufficient_evidence": false}'),
    )
    restored = TestClient(create_api(restarted)).get(f"/api/sessions/{session_id}")
    assert restored.status_code == 200
    assert restored.json()["turns"][0]["answer"] == turn["answer"]
    assert restored.json()["turns"][0]["sources"][0]["text"] == turn["sources"][0]["text"]


def test_selected_documents_persist_including_missing_ids(tmp_path: Path) -> None:
    client, _application = _client(tmp_path)
    error_doc = _upload(client, "error_code.md")
    cake_doc = _upload(client, "cake.md")
    session_id = client.post(
        "/api/sessions",
        json={
            "all_documents": False,
            "selected_document_ids": [error_doc["document_id"], cake_doc["document_id"]],
        },
    ).json()["session_id"]
    client.patch(
        f"/api/sessions/{session_id}",
        json={"all_documents": False, "selected_document_ids": [error_doc["document_id"]]},
    )
    client.delete(f"/api/documents/{error_doc['document_id']}")
    loaded = client.get(f"/api/sessions/{session_id}").json()
    assert loaded["missing_selected_count"] == 1
    assert error_doc["document_id"] in loaded["selected_document_ids"]
    assert cake_doc["document_id"] not in loaded["selected_document_ids"]


def test_all_documents_scope_persists_across_restart(tmp_path: Path) -> None:
    client, application = _client(tmp_path)
    _upload(client)
    session_id = client.post("/api/sessions", json={"all_documents": True}).json()["session_id"]
    loaded = client.get(f"/api/sessions/{session_id}").json()
    assert loaded["all_documents"] is True
    restarted = create_application(
        _settings(tmp_path),
        store=SqliteDocumentStore(application.settings.database_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=ScriptedLLM('{"answer": "ok [S1].", "insufficient_evidence": false}'),
    )
    restored = TestClient(create_api(restarted)).get(f"/api/sessions/{session_id}")
    assert restored.status_code == 200
    assert restored.json()["all_documents"] is True
    assert restored.json()["selected_document_ids"] == []


def test_none_document_scope_persists_and_is_not_coerced_to_all(tmp_path: Path) -> None:
    client, application = _client(tmp_path)
    _upload(client)
    session_id = client.post(
        "/api/sessions",
        json={"all_documents": False, "selected_document_ids": []},
    ).json()["session_id"]
    loaded = client.get(f"/api/sessions/{session_id}").json()
    assert loaded["all_documents"] is False
    assert loaded["selected_document_ids"] == []
    patched = client.patch(
        f"/api/sessions/{session_id}",
        json={"all_documents": False, "selected_document_ids": []},
    )
    assert patched.status_code == 200
    assert patched.json()["all_documents"] is False
    restarted = create_application(
        _settings(tmp_path),
        store=SqliteDocumentStore(application.settings.database_path),
        embedder=HashingEmbeddingModel(dimension=32),
        reranker=OverlapReranker(),
        llm=ScriptedLLM('{"answer": "ok [S1].", "insufficient_evidence": false}'),
    )
    restored = TestClient(create_api(restarted)).get(f"/api/sessions/{session_id}")
    assert restored.status_code == 200
    assert restored.json()["all_documents"] is False
    assert restored.json()["selected_document_ids"] == []


def test_session_delete_does_not_remove_documents(tmp_path: Path) -> None:
    client, application = _client(tmp_path)
    doc = _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    client.post("/api/ask", json={"question": "What failed?", "session_id": session_id})
    client.delete(f"/api/sessions/{session_id}")
    assert application.store.get_by_id(doc["document_id"]) is not None
    assert application.store.count_chunks(doc["document_id"]) >= 1
    listed = client.get("/api/documents").json()["documents"]
    assert listed[0]["document_id"] == doc["document_id"]


def test_deleted_document_keeps_historical_source_snapshot(tmp_path: Path) -> None:
    client, _application = _client(tmp_path)
    doc = _upload(client)
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    asked = client.post(
        "/api/ask",
        json={"question": "What is ERR_CONNECTION_REFUSED?", "session_id": session_id},
    )
    snapshot = asked.json()["sources"][0]["text"]
    client.delete(f"/api/documents/{doc['document_id']}")
    loaded = client.get(f"/api/sessions/{session_id}").json()
    assert loaded["turns"][0]["sources"][0]["text"] == snapshot
    assert loaded["turns"][0]["sources"][0]["filename"] == "error_code.md"


def test_reindex_does_not_rewrite_historical_snapshot(tmp_path: Path) -> None:
    client, application = _client(tmp_path)
    doc = _upload(client, "error_code.md")
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    asked = client.post(
        "/api/ask",
        json={"question": "What is ERR_CONNECTION_REFUSED?", "session_id": session_id},
    )
    old_text = asked.json()["sources"][0]["text"]
    record = application.store.get_by_id(doc["document_id"])
    assert record is not None
    Path(record.source_path).write_text(
        "# Dessert\n\nChocolate cake requires cocoa after the refresh.\n",
        encoding="utf-8",
    )
    reindexed = client.post(f"/api/documents/{doc['document_id']}/reindex")
    assert reindexed.status_code == 200
    loaded = client.get(f"/api/sessions/{session_id}").json()
    assert loaded["turns"][0]["sources"][0]["text"] == old_text
    assert "ERR_CONNECTION_REFUSED" in old_text


def test_session_followup_uses_persisted_bounded_history(tmp_path: Path) -> None:
    llm = ScriptedLLM(
        (
            '{"answer": "Willow Reed and Ash Calder [S1].", "insufficient_evidence": false}',
            '{"answer": "They marry later [S1].", "insufficient_evidence": false}',
        )
    )
    client, _application = _client(tmp_path, llm)
    path = Path(__file__).resolve().parents[2] / "evaluation" / "corpus" / "followup" / "willow_and_ash.md"
    if not path.exists():
        path = LEXICAL / "error_code.md"
        client.post(
            "/api/documents",
            files={"file": (path.name, path.read_bytes(), "text/markdown")},
        )
    else:
        client.post(
            "/api/documents",
            files={"file": (path.name, path.read_bytes(), "text/markdown")},
        )
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    first = client.post(
        "/api/ask",
        json={"question": "Who are the couple?", "session_id": session_id, "conversation": []},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/ask",
        json={"question": "Do they marry?", "session_id": session_id},
    )
    assert second.status_code == 200, second.text
    diag = second.json()["diagnostics"]
    assert diag["history_turns_used"] >= 1
    assert diag["followup_detected"] is True


def test_history_is_not_evidence_for_later_turns(tmp_path: Path) -> None:
    planted = "The launch date is March."
    llm = ScriptedLLM(
        (
            f'{{"answer": "{planted} [S1]", "insufficient_evidence": false}}',
            '{"answer": "", "insufficient_evidence": true}',
        )
    )
    client, application = _client(tmp_path, llm)
    _upload(client, "cake.md")
    session_id = client.post("/api/sessions", json={}).json()["session_id"]
    first = client.post(
        "/api/ask",
        json={"question": "What dessert is described?", "session_id": session_id},
    )
    assert first.status_code == 200
    assert planted in first.json()["answer"]
    second = client.post(
        "/api/ask",
        json={"question": "When is the launch date?", "session_id": session_id},
    )
    assert second.status_code == 200
    assert second.json()["insufficient_evidence"] is True
    evidence = llm.requests[-1].messages[2].content
    assert planted not in evidence
    assert "launch date is March" not in evidence.lower()


def test_sessionless_ask_remains_ephemeral(tmp_path: Path) -> None:
    client, application = _client(tmp_path)
    _upload(client)
    asked = client.post("/api/ask", json={"question": "What is ERR_CONNECTION_REFUSED?"})
    assert asked.status_code == 200
    assert asked.json().get("session_id") in {None, ""}
    assert application.store.list_sessions() == []


def test_migration_from_v3_preserves_documents(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE schema_version (version INTEGER NOT NULL);
        INSERT INTO schema_version (version) VALUES (3);
        CREATE TABLE documents (
            document_id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            content_type TEXT NOT NULL,
            checksum_sha256 TEXT NOT NULL,
            byte_size INTEGER NOT NULL,
            ingested_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            parse_status TEXT NOT NULL,
            parser_id TEXT,
            warning_count INTEGER NOT NULL DEFAULT 0,
            page_count INTEGER,
            parsed_json TEXT,
            error_type TEXT,
            error_message TEXT
        );
        INSERT INTO documents VALUES (
            'doc-legacy', '/tmp/legacy.md', 'legacy.md', 'text/markdown',
            'abc', 12, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00',
            'parsed', 'markdown.v1', 0, NULL, NULL, NULL, NULL
        );
        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunker_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            text TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            char_count INTEGER NOT NULL,
            approx_token_count INTEGER NOT NULL,
            page_start INTEGER,
            page_end INTEGER,
            section_path TEXT NOT NULL,
            source_block_start INTEGER NOT NULL,
            source_block_end INTEGER NOT NULL,
            warnings TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
        );
        CREATE TABLE vector_indexes (
            index_id TEXT PRIMARY KEY,
            collection_name TEXT NOT NULL UNIQUE,
            embedding_model_id TEXT NOT NULL,
            chunker_id TEXT NOT NULL,
            dimension INTEGER NOT NULL,
            metric TEXT NOT NULL,
            normalized INTEGER NOT NULL,
            schema_version INTEGER NOT NULL,
            backend TEXT NOT NULL,
            status TEXT NOT NULL,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            error_message TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    store = SqliteDocumentStore(db_path)
    assert store.schema_version() == SCHEMA_VERSION
    assert store.get_by_id("doc-legacy") is not None
    assert store.list_sessions() == []
    store.create_session(
        "sess1",
        title="New research",
        created_at="2026-08-18T00:00:00+00:00",
    )
    assert store.get_session("sess1") is not None
    assert store.get_by_id("doc-legacy") is not None
