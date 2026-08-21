from pathlib import Path

from research_assistant.chunking.config import ChunkingConfig
from research_assistant.chunking.service import ChunkingService
from research_assistant.core.types import ChunkingOutcome
from research_assistant.ingestion.service import IngestionService
from tests.conftest import FIXTURES


def _small() -> ChunkingConfig:
    return ChunkingConfig(
        strategy="structure",
        target_chars=80,
        max_chars=140,
        min_chars=20,
        overlap_chars=15,
    )


def test_persistence_round_trip_and_idempotency(
    service: IngestionService, store, settings
) -> None:
    ingested = service.ingest(FIXTURES / "markdown" / "long_article.md")
    assert ingested.document is not None
    chunking = ChunkingService(settings=settings, store=store)
    first = chunking.chunk_document(ingested.document.document_id, _small())
    second = chunking.chunk_document(ingested.document.document_id, _small())
    assert first.ok and second.ok
    assert first.outcome is ChunkingOutcome.CREATED
    assert second.outcome is ChunkingOutcome.REPLACED
    loaded = chunking.list_chunks(ingested.document.document_id, first.chunker_id)
    assert [c.chunk_id for c in loaded] == [c.chunk_id for c in first.chunks]
    assert [c.text for c in loaded] == [c.text for c in first.chunks]
    assert [c.chunk_id for c in second.chunks] == [c.chunk_id for c in first.chunks]
    rows = store.list_chunks(ingested.document.document_id, first.chunker_id)
    assert len(rows) == len(first.chunks)


def test_changed_config_does_not_mix_with_old_rows(
    service: IngestionService, store, settings
) -> None:
    ingested = service.ingest(FIXTURES / "markdown" / "long_article.md")
    assert ingested.document is not None
    chunking = ChunkingService(settings=settings, store=store)
    a = _small()
    b = ChunkingConfig(
        strategy="window",
        target_chars=60,
        max_chars=90,
        min_chars=15,
        overlap_chars=10,
    )
    first = chunking.chunk_document(ingested.document.document_id, a)
    second = chunking.chunk_document(ingested.document.document_id, b)
    assert first.chunker_id != second.chunker_id
    stored_a = store.list_chunks(ingested.document.document_id, first.chunker_id)
    stored_b = store.list_chunks(ingested.document.document_id, second.chunker_id)
    assert len(stored_a) == len(first.chunks)
    assert len(stored_b) == len(second.chunks)


def test_reingest_changed_content_drops_stale_chunks(
    service: IngestionService, store, settings, tmp_path: Path
) -> None:
    path = tmp_path / "note.md"
    path.write_text("# One\n\n" + ("alpha " * 40) + "\n", encoding="utf-8")
    first_ingest = service.ingest(path)
    assert first_ingest.document is not None
    chunking = ChunkingService(settings=settings, store=store)
    chunked = chunking.chunk_document(first_ingest.document.document_id, _small())
    assert chunked.chunks
    path.write_text("# Two\n\n" + ("beta " * 40) + "\n", encoding="utf-8")
    second_ingest = service.ingest(path)
    assert second_ingest.outcome.value == "updated"
    leftover = store.list_chunks(first_ingest.document.document_id)
    assert leftover == []
    again = chunking.chunk_document(first_ingest.document.document_id, _small())
    assert again.chunks
    assert all("beta" in c.text or "Two" in c.text for c in again.chunks)
    assert all("alpha" not in c.text for c in again.chunks)


def test_source_blocks_survive_structure_chunking(
    service: IngestionService, store, settings
) -> None:
    ingested = service.ingest(FIXTURES / "markdown" / "structure.md")
    assert ingested.parsed is not None
    chunking = ChunkingService(settings=settings, store=store)
    result = chunking.chunk_parsed(ingested.parsed, _small())
    blob = "\n".join(c.text for c in result)
    for block in ingested.parsed.blocks:
        if block.text.strip():
            assert block.text in blob or block.text.replace("\n", "\n") in blob


def test_pdf_page_provenance_round_trip(
    service: IngestionService, store, settings
) -> None:
    ingested = service.ingest(FIXTURES / "pdf" / "multi_page.pdf")
    assert ingested.document is not None
    cfg = ChunkingConfig(
        strategy="structure",
        target_chars=40,
        max_chars=80,
        min_chars=10,
        overlap_chars=0,
    )
    chunking = ChunkingService(settings=settings, store=store)
    result = chunking.chunk_document(ingested.document.document_id, cfg)
    assert result.chunks
    for chunk in result.chunks:
        assert chunk.page_start is not None
        assert chunk.page_end is not None
        assert chunk.page_start <= chunk.page_end
    stored = store.list_chunks(ingested.document.document_id, cfg.chunker_id)
    assert stored[0].page_start == result.chunks[0].page_start


def test_empty_parsed_document_is_empty_outcome(
    service: IngestionService, store, settings
) -> None:
    ingested = service.ingest(FIXTURES / "txt" / "empty.txt")
    assert ingested.document is not None
    chunking = ChunkingService(settings=settings, store=store)
    result = chunking.chunk_document(ingested.document.document_id, _small())
    assert result.outcome is ChunkingOutcome.EMPTY
    assert result.chunks == ()
