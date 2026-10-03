"""Composition root. Callers (CLI, tests, and the HTTP API) share one wiring."""

from __future__ import annotations

from dataclasses import dataclass

from research_assistant.chunking.service import ChunkingService
from research_assistant.context.builder import CitationAwareContextBuilder
from research_assistant.conversation.heuristic import HeuristicQueryResolver
from research_assistant.conversation.protocol import QueryResolver
from research_assistant.core.settings import Settings, load_settings
from research_assistant.embeddings.protocol import EmbeddingModel
from research_assistant.generation.protocol import LLMClient
from research_assistant.generation.rag import RAGService
from research_assistant.generation.service import GroundedGenerationService
from research_assistant.indexing.invalidation import RegistryVectorInvalidator
from research_assistant.indexing.protocol import VectorStore
from research_assistant.indexing.qdrant_store import qdrant_store_for
from research_assistant.indexing.service import IndexingService
from research_assistant.ingestion.service import IngestionService
from research_assistant.reranking.protocol import Reranker
from research_assistant.reranking.service import RerankingService
from research_assistant.retrieval.dense import DenseSearchService
from research_assistant.retrieval.hybrid import HybridSearchService
from research_assistant.retrieval.lexical import LexicalRetriever
from research_assistant.retrieval.pipeline import EvidencePipeline
from research_assistant.storage.sqlite import SqliteDocumentStore


@dataclass(frozen=True)
class Application:
    settings: Settings
    store: SqliteDocumentStore
    ingest: IngestionService
    chunking: ChunkingService
    indexing: IndexingService
    search: DenseSearchService
    lexical: LexicalRetriever
    hybrid: HybridSearchService
    reranker: RerankingService
    context: CitationAwareContextBuilder
    evidence: EvidencePipeline
    generation: GroundedGenerationService
    rag: RAGService


def create_application(
    settings: Settings | None = None,
    *,
    store: SqliteDocumentStore | None = None,
    embedder: EmbeddingModel | None = None,
    vector_store: VectorStore | None = None,
    reranker: Reranker | None = None,
    llm: LLMClient | None = None,
    resolver: QueryResolver | None = None,
) -> Application:
    """Wire ingest through grounded generation. Stages stay independently testable."""
    resolved = settings or load_settings()
    document_store = store or SqliteDocumentStore(
        resolved.database_path,
        busy_timeout_ms=resolved.sqlite_busy_timeout_ms,
    )
    vectors = vector_store or qdrant_store_for(resolved.vector_index_path)
    invalidator = RegistryVectorInvalidator(document_store, vectors)
    ingest = IngestionService(
        settings=resolved,
        store=document_store,
        invalidator=invalidator,
    )
    indexing = IndexingService(
        settings=resolved,
        store=document_store,
        embedder=embedder,
        vector_store=vectors,
    )
    search = DenseSearchService(
        settings=resolved,
        store=document_store,
        embedder=embedder,
        vector_store=vectors,
        index_health=indexing.health,
    )
    lexical = LexicalRetriever(settings=resolved, store=document_store, index_health=indexing.health)
    hybrid = HybridSearchService(
        settings=resolved,
        dense=search,
        lexical=lexical,
    )
    chunking = ChunkingService(settings=resolved, store=document_store)
    ranking = RerankingService(settings=resolved, reranker=reranker)
    context = CitationAwareContextBuilder(settings=resolved)
    evidence = EvidencePipeline(
        hybrid=hybrid,
        reranker=ranking,
        context=context,
        settings=resolved,
    )
    generation = GroundedGenerationService(settings=resolved, llm=llm)
    query_resolver = resolver or HeuristicQueryResolver(
        window=resolved.conversation_window
    )
    rag = RAGService(
        evidence=evidence,
        generation=generation,
        resolver=query_resolver,
        conversation_window=resolved.conversation_window,
    )
    return Application(
        settings=resolved,
        store=document_store,
        ingest=ingest,
        chunking=chunking,
        indexing=indexing,
        search=search,
        lexical=lexical,
        hybrid=hybrid,
        reranker=ranking,
        context=context,
        evidence=evidence,
        generation=generation,
        rag=rag,
    )
