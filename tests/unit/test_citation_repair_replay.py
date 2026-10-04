"""Offline replay input checks; no model requests or benchmark TEST rows."""
import json
import sqlite3

import pytest

from scripts import replay_citation_repair as replay


def _source(tmp_path, monkeypatch):
    report = {"run_id": replay.SOURCE_RUN, "config": {"split": "dev"}, "examples": [
        {"example_id": item, "split": "dev", "first_pass_validation_status": "missing_citations", "repair_attempts": 1}
        for item in replay.POPULATION
    ]}
    path = tmp_path / "source.json"
    path.write_text(json.dumps(report))
    monkeypatch.setattr(replay, "SOURCE_SHA", replay.sha256(path))
    return path, report


def test_replay_requires_exact_source_hash(tmp_path, monkeypatch):
    path, _ = _source(tmp_path, monkeypatch)
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="SHA"):
        replay.load_source(path)


@pytest.mark.parametrize("mutation", ["split", "population", "row_split"])
def test_replay_rejects_changed_scope_even_with_matching_hash(tmp_path, monkeypatch, mutation):
    path, report = _source(tmp_path, monkeypatch)
    if mutation == "split":
        report["config"]["split"] = "non-dev"
    elif mutation == "population":
        report["examples"].pop()
    else:
        report["examples"][0]["split"] = "non-dev"
    path.write_text(json.dumps(report))
    monkeypatch.setattr(replay, "SOURCE_SHA", replay.sha256(path))
    with pytest.raises(ValueError):
        replay.load_source(path)


def test_replay_only_selects_saved_missing_citation_repairs(tmp_path, monkeypatch):
    path, report = _source(tmp_path, monkeypatch)
    report["examples"].append({"example_id": "unused", "split": "dev", "first_pass_validation_status": "valid", "repair_attempts": 0})
    path.write_text(json.dumps(report))
    monkeypatch.setattr(replay, "SOURCE_SHA", replay.sha256(path))
    _, rows = replay.load_source(path)
    assert tuple(row["example_id"] for row in rows) == replay.POPULATION


def test_saved_bundle_preserves_exact_excerpt_and_restores_only_headers():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE chunks (chunk_id, document_id, text, page_start, page_end, section_path, content_hash, chunker_id)")
    connection.execute("CREATE TABLE documents (document_id, filename)")
    connection.execute("INSERT INTO documents VALUES ('d1', 'record.md')")
    connection.execute("INSERT INTO chunks VALUES ('c1','d1',?,2,3,?, 'hash', 'chunker')", (" A.\n B. omitted", '["Section"]'))
    row = {"context_blocks": [{"citation_id": "S1", "chunk_id": "c1", "document_id": "d1", "filename": "record.md", "text": " A.\n B.", "truncated": True}], "context_citation_ids": ["S1"]}
    bundle = replay.saved_bundle(row, connection)
    assert bundle.rendered_text == "[S1]\nSource: record.md\nPages: 2–3\nSection: Section\nEvidence:\n A.\n B."
    assert bundle.items[0].text == row["context_blocks"][0]["text"]
    assert bundle.query == ""
    row["context_blocks"][0]["text"] = "changed"
    with pytest.raises(ValueError, match="excerpt"):
        replay.saved_bundle(row, connection)
    connection.close()
