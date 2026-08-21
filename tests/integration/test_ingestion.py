from pathlib import Path
import shutil

from research_assistant.core.settings import Settings
from research_assistant.core.types import IngestOutcome, ParseStatus, VectorPurgeStatus
from research_assistant.ingestion.checksum import sha256_bytes
from research_assistant.ingestion.identity import document_id_for_path
from research_assistant.ingestion.service import IngestionService
from tests.conftest import FIXTURES


def test_ingest_txt_success(service: IngestionService) -> None:
    path = FIXTURES / "txt" / "paragraphs_unicode.txt"
    result = service.ingest(path)
    assert result.outcome is IngestOutcome.CREATED
    assert result.ok
    assert result.document is not None
    assert result.document.parse_status is ParseStatus.PARSED
    assert result.parsed is not None
    assert len(result.parsed.blocks) == 3


def test_ingest_markdown_success(service: IngestionService) -> None:
    result = service.ingest(FIXTURES / "markdown" / "structure.md")
    assert result.outcome is IngestOutcome.CREATED
    assert result.parsed is not None
    kinds = {block.kind.value for block in result.parsed.blocks}
    assert "heading" in kinds
    assert "code_block" in kinds


def test_ingest_pdf_success(service: IngestionService) -> None:
    result = service.ingest(FIXTURES / "pdf" / "multi_page.pdf")
    assert result.outcome is IngestOutcome.CREATED
    assert result.document is not None
    assert result.document.page_count == 3
    assert result.parsed is not None
    assert all(block.page is not None for block in result.parsed.blocks)


def test_case_a_same_path_same_content_is_idempotent(
    service: IngestionService, tmp_path: Path
) -> None:
    path = tmp_path / "note.txt"
    path.write_text("stable", encoding="utf-8")
    first = service.ingest(path)
    second = service.ingest(path)
    assert first.outcome is IngestOutcome.CREATED
    assert second.outcome is IngestOutcome.UNCHANGED
    assert first.document is not None and second.document is not None
    assert first.document.document_id == second.document.document_id
    assert first.document.checksum_sha256 == second.document.checksum_sha256
    assert first.document.ingested_at == second.document.ingested_at


def test_case_b_same_path_changed_content_updates_record(
    service: IngestionService, tmp_path: Path
) -> None:
    path = tmp_path / "note.txt"
    path.write_text("version one", encoding="utf-8")
    first = service.ingest(path)
    path.write_text("version two", encoding="utf-8")
    second = service.ingest(path)
    assert first.document is not None and second.document is not None
    assert second.outcome is IngestOutcome.UPDATED
    assert first.document.document_id == second.document.document_id
    assert first.document.checksum_sha256 != second.document.checksum_sha256
    assert first.document.ingested_at == second.document.ingested_at
    assert second.document.updated_at >= first.document.updated_at
    assert second.parsed is not None
    assert "version two" in second.parsed.full_text()
    assert first.vector_purge_status is VectorPurgeStatus.NOT_APPLICABLE
    assert second.vector_purge_status is VectorPurgeStatus.NOOP


def test_case_c_different_path_same_content_are_separate_documents(
    service: IngestionService, tmp_path: Path
) -> None:
    src = FIXTURES / "txt" / "paragraphs_unicode.txt"
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    shutil.copy(src, a)
    shutil.copy(src, b)
    first = service.ingest(a)
    second = service.ingest(b)
    assert first.outcome is IngestOutcome.CREATED
    assert second.outcome is IngestOutcome.CREATED
    assert first.document is not None and second.document is not None
    assert first.document.document_id != second.document.document_id
    assert first.document.checksum_sha256 == second.document.checksum_sha256
    assert first.document.checksum_sha256 == sha256_bytes(src.read_bytes())
    assert document_id_for_path(a) == first.document.document_id


def test_case_d_unsupported_file_fails_without_record(
    service: IngestionService,
) -> None:
    result = service.ingest(FIXTURES / "unsupported" / "note.html")
    assert result.outcome is IngestOutcome.FAILED
    assert result.error_type == "unsupported_type"
    assert result.document is None


def test_case_e_decode_failure_persists_failed_status(
    service: IngestionService,
) -> None:
    result = service.ingest(FIXTURES / "txt" / "invalid_utf8.txt")
    assert result.outcome is IngestOutcome.FAILED
    assert result.error_type == "decode_error"
    assert result.document is not None
    assert result.document.parse_status is ParseStatus.FAILED
    stored = service.get_document(result.document.document_id)
    assert stored is not None
    assert stored.parse_status is ParseStatus.FAILED
    assert stored.parsed_json is None


def test_case_e_corrupt_pdf_persists_failed_status(service: IngestionService) -> None:
    result = service.ingest(FIXTURES / "pdf" / "corrupt.pdf")
    assert result.outcome is IngestOutcome.FAILED
    assert result.error_type == "parse_error"
    assert result.document is not None
    assert result.document.parse_status is ParseStatus.FAILED


def test_missing_file_and_directory(service: IngestionService, tmp_path: Path) -> None:
    missing = service.ingest(tmp_path / "nope.txt")
    assert missing.error_type == "not_found"
    assert missing.document is None
    directory = service.ingest(tmp_path)
    assert directory.error_type == "is_directory"


def test_too_large_file(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "docs.db",
        log_level="WARNING",
        max_file_bytes=8,
    )
    service = IngestionService(settings=settings)
    path = tmp_path / "big.txt"
    path.write_text("0123456789", encoding="utf-8")
    result = service.ingest(path)
    assert result.error_type == "too_large"
    assert result.document is None


def test_persistence_round_trip(service: IngestionService) -> None:
    path = FIXTURES / "markdown" / "structure.md"
    created = service.ingest(path)
    assert created.document is not None
    stored = service.get_document(created.document.document_id)
    assert stored is not None
    parsed = stored.parsed_document()
    assert parsed is not None
    assert parsed.parser_id == "markdown.v1"
    assert [block.to_dict() for block in parsed.blocks] == [
        block.to_dict() for block in created.parsed.blocks  # type: ignore[union-attr]
    ]


def test_failed_ingest_is_idempotent_without_force(
    service: IngestionService,
) -> None:
    path = FIXTURES / "txt" / "invalid_utf8.txt"
    first = service.ingest(path)
    second = service.ingest(path)
    assert first.outcome is IngestOutcome.FAILED
    assert second.outcome is IngestOutcome.UNCHANGED
    assert not first.ok
    assert not second.ok
    assert first.document is not None and second.document is not None
    assert first.document.document_id == second.document.document_id
    assert second.document.parse_status is ParseStatus.FAILED
