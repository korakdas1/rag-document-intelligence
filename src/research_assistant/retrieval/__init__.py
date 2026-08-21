"""Dense, lexical, and hybrid retrieval."""

from research_assistant.retrieval.dense import DenseSearchResult, DenseSearchService
from research_assistant.retrieval.filters import RetrievalFilter
from research_assistant.retrieval.fusion import ReciprocalRankFusion
from research_assistant.retrieval.hybrid import HybridSearchResult, HybridSearchService
from research_assistant.retrieval.lexical import LexicalRetriever, LexicalSearchResult
from research_assistant.retrieval.models import RetrievalHit

__all__ = [
    "DenseSearchResult",
    "DenseSearchService",
    "HybridSearchResult",
    "HybridSearchService",
    "LexicalRetriever",
    "LexicalSearchResult",
    "ReciprocalRankFusion",
    "RetrievalFilter",
    "RetrievalHit",
]
