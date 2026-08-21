from pathlib import Path

from research_assistant.app import create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.core.settings import Settings
from research_assistant.embeddings.hashing import HashingEmbeddingModel
from research_assistant.retrieval.filters import RetrievalFilter
from tests.conftest import FIXTURES


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "docs.db",
        log_level="WARNING",
        max_file_bytes=50 * 1024 * 1024,
        embedding_model_name="hashing",
        embedding_device="cpu",
        vector_index_path=tmp_path / "qdrant",
        default_top_k=8,
    )


def _app(tmp_path: Path):
    return create_application(
        _settings(tmp_path),
        embedder=HashingEmbeddingModel(dimension=32),
    )


def test_document_and_filename_filters(tmp_path: Path) -> None:
    app = _app(tmp_path)
    cfg = ChunkingConfig(
        strategy="structure",
        target_chars=400,
        max_chars=600,
        min_chars=10,
        overlap_chars=0,
    )
    left = tmp_path / "alpha.md"
    right = tmp_path / "beta.md"
    left.write_text("# ML\n\nGradient descent trains neural networks.\n", encoding="utf-8")
    right.write_text("# ML\n\nGradient descent trains neural networks.\n", encoding="utf-8")
    a = app.ingest.ingest(left)
    b = app.ingest.ingest(right)
    assert a.document and b.document
    chunker_id = app.chunking.chunk_document(a.document.document_id, cfg).chunker_id
    app.chunking.chunk_document(b.document.document_id, cfg)
    app.indexing.index_document(a.document.document_id, chunker_id)
    app.indexing.index_document(b.document.document_id, chunker_id)
    filt = RetrievalFilter(document_ids=(a.document.document_id,))
    for mode in ("dense", "lexical", "hybrid"):
        result = app.hybrid.search(
            "gradient descent",
            chunker_id=chunker_id,
            mode=mode,
            top_k=8,
            filters=filt,
        )
        assert result.hits
        assert {hit.document_id for hit in result.hits} == {a.document.document_id}
    by_name = app.hybrid.search(
        "gradient descent",
        chunker_id=chunker_id,
        mode="lexical",
        filters=RetrievalFilter(filenames=("beta.md",)),
    )
    assert by_name.hits
    assert {hit.filename for hit in by_name.hits} == {"beta.md"}
    none = app.hybrid.search(
        "gradient descent",
        chunker_id=chunker_id,
        mode="hybrid",
        filters=RetrievalFilter(document_ids=("missing-doc",)),
    )
    assert none.hits == ()
    app.indexing.vector_store.close()


def test_page_overlap_filter_on_pdf(tmp_path: Path) -> None:
    app = _app(tmp_path)
    ingested = app.ingest.ingest(FIXTURES / "pdf" / "multi_page.pdf")
    assert ingested.document is not None
    cfg = ChunkingConfig(
        strategy="structure",
        target_chars=80,
        max_chars=200,
        min_chars=5,
        overlap_chars=0,
    )
    chunked = app.chunking.chunk_document(ingested.document.document_id, cfg)
    app.indexing.index_document(ingested.document.document_id, chunked.chunker_id)
    page2 = app.hybrid.search(
        "page",
        chunker_id=chunked.chunker_id,
        mode="lexical",
        filters=RetrievalFilter(page=2),
    )
    assert page2.hits
    for hit in page2.hits:
        assert hit.page_start is not None and hit.page_end is not None
        assert hit.page_start <= 2 <= hit.page_end
    app.indexing.vector_store.close()


def test_section_prefix_filter(tmp_path: Path) -> None:
    app = _app(tmp_path)
    path = tmp_path / "paper.md"
    path.write_text(
        "# Methods\n\nTraining uses Adam.\n\n# Results\n\nAccuracy improved.\n",
        encoding="utf-8",
    )
    ingested = app.ingest.ingest(path)
    assert ingested.document is not None
    cfg = ChunkingConfig(
        strategy="structure",
        target_chars=80,
        max_chars=200,
        min_chars=5,
        overlap_chars=0,
    )
    chunked = app.chunking.chunk_document(ingested.document.document_id, cfg)
    app.indexing.index_document(ingested.document.document_id, chunked.chunker_id)
    methods = app.hybrid.search(
        "Adam Accuracy",
        chunker_id=chunked.chunker_id,
        mode="lexical",
        filters=RetrievalFilter(section_prefix=("Methods",)),
    )
    assert methods.hits
    assert all(hit.section_path[:1] == ("Methods",) for hit in methods.hits)
    app.indexing.vector_store.close()
