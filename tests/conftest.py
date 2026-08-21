"""Shared paths and ingestion fixtures. Tests never use developer home paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_assistant.core.settings import Settings
from research_assistant.ingestion.service import IngestionService
from research_assistant.storage.sqlite import SqliteDocumentStore

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "docs.db",
        log_level="WARNING",
        max_file_bytes=50 * 1024 * 1024,
        embedding_model_name="hashing",
        vector_index_path=tmp_path / "qdrant",
        reranker_model_name="overlap",
        llm_provider="scripted",
        llm_model_name="scripted.v1",
    )


@pytest.fixture
def store(settings: Settings) -> SqliteDocumentStore:
    return SqliteDocumentStore(settings.database_path)


@pytest.fixture
def service(settings: Settings, store: SqliteDocumentStore) -> IngestionService:
    return IngestionService(settings=settings, store=store)
