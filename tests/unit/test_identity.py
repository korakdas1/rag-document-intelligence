from pathlib import Path

from research_assistant.ingestion.identity import document_id_for_path


def test_identity_is_stable_for_same_path(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    assert document_id_for_path(path) == document_id_for_path(path)


def test_identity_differs_for_different_paths_same_content(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("same", encoding="utf-8")
    b.write_text("same", encoding="utf-8")
    assert document_id_for_path(a) != document_id_for_path(b)


def test_identity_does_not_depend_on_content(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("v1", encoding="utf-8")
    first = document_id_for_path(path)
    path.write_text("v2", encoding="utf-8")
    assert document_id_for_path(path) == first
