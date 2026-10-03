"""Direct API scope boundaries, independent of browser selection state."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from tests.integration.test_sessions import _client
from research_assistant.indexing.identity import collection_name_for
from research_assistant.api.library import DocumentLibrary
from research_assistant.generation.scripted import ScriptedLLM


def upload(client, name: str) -> str:
    response = client.post(
        "/api/documents",
        files={"file": (f"{name}.md", f"# {name}\n\nOrchard evidence from {name}.", "text/markdown")},
    )
    assert response.status_code == 200, response.text
    return response.json()["document"]["document_id"]


def session(client, *, all_documents=False, ids=()) -> str:
    response = client.post(
        "/api/sessions",
        json={"all_documents": all_documents, "selected_document_ids": list(ids)},
    )
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def ask(client, session_id=None, **fields):
    return client.post(
        "/api/ask",
        json={
            "question": "What orchard evidence is available?",
            "retrieval_mode": "lexical",
            "rerank": False,
            "session_id": session_id,
            **fields,
        },
    )


@pytest.mark.parametrize("legacy_ids", [None, []], ids=["omitted", "empty"])
def test_saved_subset_cannot_be_bypassed(tmp_path: Path, legacy_ids) -> None:
    client, _app = _client(tmp_path)
    a, b = upload(client, "Alpha"), upload(client, "Beta")
    saved = session(client, ids=[a])
    response = ask(client, saved, **({} if legacy_ids is None else {"document_ids": legacy_ids}))
    if legacy_ids is None:
        assert response.status_code == 200, response.text
        assert {source["document_id"] for source in response.json()["sources"]} == {a}
    else:
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "scope_mismatch"
    assert b not in {source["document_id"] for source in response.json().get("sources", [])}


def test_saved_none_stops_before_pipeline(tmp_path: Path, monkeypatch) -> None:
    client, app = _client(tmp_path)
    upload(client, "Alpha")
    saved = session(client)
    calls = []
    original = app.rag.answer

    def record_call(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(app.rag, "answer", record_call)
    response = ask(client, saved)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "no_documents_selected"
    assert calls == []


def source_ids(response):
    assert response.status_code == 200, response.text
    return {source["document_id"] for source in response.json()["sources"]}


def forbid_pipeline(app, monkeypatch):
    for component, method in (
        (app.rag, "answer"), (app.search, "search"), (app.lexical, "search"),
        (app.reranker, "rerank"), (app.generation, "generate"),
    ):
        monkeypatch.setattr(component, method, Mock(side_effect=AssertionError("Pipeline must not run")))


@pytest.mark.parametrize("mode", ["dense", "lexical", "hybrid"])
def test_saved_subset_and_legacy_assertions_in_every_mode(tmp_path, mode, monkeypatch):
    client, app = _client(tmp_path)
    a, b = upload(client, "Alpha"), upload(client, "Beta")
    saved = session(client, ids=[a])
    assert source_ids(ask(client, saved, retrieval_mode=mode)) == {a}
    assert source_ids(ask(client, saved, retrieval_mode=mode, document_ids=[a, a])) == {a}
    forbid_pipeline(app, monkeypatch)
    for ids in ([a, b], [b], [], ["unknown"]):
        response = ask(client, saved, retrieval_mode=mode, document_ids=ids)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "scope_mismatch"


@pytest.mark.parametrize("mode", ["dense", "lexical", "hybrid"])
def test_none_cannot_be_overridden_and_does_no_health_or_model_work(tmp_path, mode, monkeypatch):
    llm = ScriptedLLM("unused")
    client, app = _client(tmp_path, llm)
    a = upload(client, "Alpha")
    saved = session(client)
    forbid_pipeline(app, monkeypatch)
    monkeypatch.setattr(app.indexing.health, "inspect", Mock(side_effect=AssertionError("No inventory needed")))
    for fields in ({}, {"document_ids": []}, {"document_ids": [a]}):
        response = ask(client, saved, retrieval_mode=mode, **fields)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "no_documents_selected"
    assert not llm.requests


@pytest.mark.parametrize("all_documents", [True, False])
def test_new_upload_is_included_only_in_dynamic_all(tmp_path, all_documents):
    client, _app = _client(tmp_path)
    a = upload(client, "Alpha")
    saved = session(client, all_documents=all_documents, ids=[a])
    assert source_ids(ask(client, saved)) == {a}
    b = upload(client, "Beta")
    assert source_ids(ask(client, saved)) == ({a, b} if all_documents else {a})


@pytest.mark.parametrize("delete_all", [False, True])
def test_deleted_subset_is_preserved_and_fails_closed(tmp_path, delete_all, monkeypatch):
    client, app = _client(tmp_path)
    a, b = upload(client, "Alpha"), upload(client, "Beta")
    upload(client, "Outside")
    saved = session(client, ids=[a, b])
    for doc_id in ([a, b] if delete_all else [b]):
        assert client.delete(f"/api/documents/{doc_id}").status_code == 200
    loaded = client.get(f"/api/sessions/{saved}").json()
    assert loaded["selected_document_ids"] == [a, b]
    assert loaded["missing_selected_count"] == (2 if delete_all else 1)
    assert not loaded["all_documents"]
    # Renaming must not erase or revalidate an old selection.
    assert client.patch(f"/api/sessions/{saved}", json={"title": "Retained scope"}).status_code == 200
    forbid_pipeline(app, monkeypatch)
    response = ask(client, saved)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "selected_documents_unavailable"
    assert app.store.get_session(saved).selected_document_ids == (a, b)


def remove_vectors(app, document_id):
    chunker_id = DocumentLibrary(app).chunker_id
    health = app.indexing.health.document_index_health(document_id, chunker_id)
    app.indexing.vector_store.delete_ids(collection_name_for(health.index_id), tuple(health.actual_ids))
    assert app.store.count_chunks(document_id, chunker_id) > 0


@pytest.mark.parametrize("mode", ["dense", "lexical", "hybrid"])
@pytest.mark.parametrize("damage", ["vectors", "failed", "building"])
def test_unavailable_subset_fails_while_all_excludes_unready_document(tmp_path, mode, damage, monkeypatch):
    client, app = _client(tmp_path)
    a, b = upload(client, "Alpha"), upload(client, "Beta")
    subset = session(client, ids=[a, b])
    all_docs = session(client, all_documents=True)
    if damage == "vectors":
        remove_vectors(app, b)
    else:
        index_id = app.indexing.index_id_for_chunker(DocumentLibrary(app).chunker_id)
        state = app.store.list_document_indexes(index_id)[b]
        app.store.begin_document_indexes([state])
        if damage == "failed":
            app.store.finish_document_indexes(index_id, state.attempt_id, succeeded=False)
    assert source_ids(ask(client, all_docs, retrieval_mode=mode)) == {a}
    forbid_pipeline(app, monkeypatch)
    response = ask(client, subset, retrieval_mode=mode)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "selected_documents_unavailable"


@pytest.mark.parametrize("with_chunks", [False, True])
def test_no_searchable_documents_does_not_call_pipeline(tmp_path, with_chunks, monkeypatch):
    llm = ScriptedLLM("unused")
    client, app = _client(tmp_path, llm)
    if with_chunks:
        remove_vectors(app, upload(client, "Alpha"))
    saved = session(client, all_documents=True)
    forbid_pipeline(app, monkeypatch)
    for session_id in (saved, None):
        response = ask(client, session_id)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "no_ready_documents"
    assert not llm.requests


def test_validate_deliberate_writes_and_normalize_duplicates(tmp_path):
    client, app = _client(tmp_path)
    a, b = upload(client, "Alpha"), upload(client, "Beta")
    saved = session(client, ids=[b, a, b])
    assert app.store.get_session(saved).selected_document_ids == (b, a)
    invalid = {"all_documents": False, "selected_document_ids": [a, "unknown"]}
    assert client.post("/api/sessions", json=invalid).status_code == 404
    assert client.patch(f"/api/sessions/{saved}", json=invalid).status_code == 404
    assert app.store.get_session(saved).selected_document_ids == (b, a)
    assert client.patch(f"/api/sessions/{saved}", json={"selected_document_ids": [a, a]}).status_code == 200
    assert app.store.get_session(saved).selected_document_ids == (a,)
    assert client.patch(f"/api/sessions/{saved}", json={"selected_document_ids": []}).status_code == 200
    assert ask(client, saved).json()["error"]["code"] == "no_documents_selected"
    assert client.patch(f"/api/sessions/{saved}", json={"all_documents": True}).status_code == 200
    assert source_ids(ask(client, saved)) == {a, b}


def test_sessionless_legacy_compatibility_and_unknown_session(tmp_path, monkeypatch):
    client, app = _client(tmp_path)
    a, b = upload(client, "Alpha"), upload(client, "Beta")
    for fields in ({}, {"document_ids": []}):
        assert source_ids(ask(client, **fields)) == {a, b}
    assert source_ids(ask(client, document_ids=[a, a])) == {a}
    assert app.store.list_sessions() == []
    forbid_pipeline(app, monkeypatch)
    assert ask(client, document_ids=["unknown"]).status_code == 404
    assert ask(client, "unknown-session").status_code == 404


def test_all_legacy_assertion_must_match_current_searchable_library(tmp_path):
    client, _app = _client(tmp_path)
    a = upload(client, "Alpha")
    saved = session(client, all_documents=True)
    assert source_ids(ask(client, saved, document_ids=[a])) == {a}
    b = upload(client, "Beta")
    assert ask(client, saved, document_ids=[a]).json()["error"]["code"] == "scope_mismatch"
    assert ask(client, saved, document_ids=[]).json()["error"]["code"] == "scope_mismatch"
    assert source_ids(ask(client, saved, document_ids=[b, a, b])) == {a, b}


def test_request_scope_snapshot_and_retry_use_current_saved_scope(tmp_path, monkeypatch):
    client, app = _client(tmp_path)
    a, b = upload(client, "Alpha"), upload(client, "Beta")
    saved = session(client, ids=[a])
    entered, resume = Event(), Event()
    original = app.rag.answer
    snapshots = []

    def pause(*args, **kwargs):
        snapshots.append(kwargs["filters"].document_ids)
        entered.set()
        assert resume.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(app.rag, "answer", pause)
    with ThreadPoolExecutor() as executor:
        pending = executor.submit(ask, client, saved)
        try:
            assert entered.wait(10)
            changed = client.patch(f"/api/sessions/{saved}", json={"selected_document_ids": [b]})
            assert changed.status_code == 200
        finally:
            resume.set()
        first = pending.result(timeout=10)
    assert source_ids(first) == {a}
    # Automatic first-answer title updates must also preserve the newer selection.
    assert app.store.get_session(saved).selected_document_ids == (b,)
    retry = ask(client, saved, replace_turn_id=first.json()["turn_id"])
    assert source_ids(retry) == {b}
    assert snapshots == [(a,), (b,)]
    assert retry.json()["turn_id"] == first.json()["turn_id"]
    assert len(app.store.list_turns(saved)) == 1


def test_one_inventory_per_ask_and_no_health_reuse_across_requests(tmp_path, monkeypatch):
    client, app = _client(tmp_path)
    a = upload(client, "Alpha")
    saved = session(client, ids=[a])
    inventory = Mock(wraps=app.indexing.vector_store.list_payloads)
    monkeypatch.setattr(app.indexing.vector_store, "list_payloads", inventory)
    assert source_ids(ask(client, saved, retrieval_mode="hybrid")) == {a}
    assert inventory.call_count == 1
    # Even a failed resolution releases the snapshot before the next request.
    assert ask(client, saved, document_ids=[]).status_code == 409
    assert inventory.call_count == 2
    remove_vectors(app, a)
    inventory.reset_mock()
    assert ask(client, saved).json()["error"]["code"] == "selected_documents_unavailable"
    assert inventory.call_count == 1
