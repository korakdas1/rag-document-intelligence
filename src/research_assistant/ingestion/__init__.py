"""Local filesystem ingestion."""

from research_assistant.ingestion.models import IngestResult
from research_assistant.ingestion.service import IngestionService

__all__ = ["IngestionService", "IngestResult"]
