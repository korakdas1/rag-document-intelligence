"""Developer CLI. Business logic lives in services, not here."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from research_assistant.app import create_application
from research_assistant.chunking.config import (
    DEFAULT_MAX_CHARS,
    DEFAULT_MIN_CHARS,
    DEFAULT_OVERLAP_CHARS,
    DEFAULT_TARGET_CHARS,
    ChunkingConfig,
)
from research_assistant.core.errors import (
    ContextError,
    EvaluationError,
    GenerationError,
    RerankError,
    RetrievalError,
)
from research_assistant.core.logging import configure_logging
from research_assistant.core.settings import load_settings
from research_assistant.core.types import RetrievalMode
from research_assistant.generation.citations import render_sources
from research_assistant.generation.rag import RAGService
from research_assistant.ingestion.service import IngestionService
from research_assistant.retrieval.filters import RetrievalFilter
from research_assistant.retrieval.hybrid import HybridSearchService
from research_assistant.retrieval.pipeline import EvidencePipeline


def main(argv: list[str] | None = None) -> int:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite database path (default: RESEARCH_ASSISTANT_DATABASE_PATH or data/processed/research_assistant.db)",
    )
    shared.add_argument(
        "--log-level",
        default=None,
        help="Logging level (default: LOG_LEVEL or INFO)",
    )
    shared.add_argument(
        "--index-path",
        type=Path,
        default=None,
        help="Qdrant local storage path",
    )
    shared.add_argument(
        "--embedding-model",
        default=None,
        help="Embedding model name, or 'hashing' for tests",
    )
    shared.add_argument(
        "--device",
        default=None,
        help="Embedding/reranker device: auto, cpu, or cuda",
    )
    shared.add_argument(
        "--reranker",
        default=None,
        help="Reranker model name, or 'overlap' for tests",
    )
    shared.add_argument(
        "--no-rerank",
        action="store_true",
        help="Skip cross-encoder reranking; keep first-stage order",
    )
    shared.add_argument(
        "--llm-model",
        default=None,
        help="LLM model name, or 'scripted' for tests",
    )
    shared.add_argument(
        "--llm-base-url",
        default=None,
        help="OpenAI-compatible base URL (default: local Ollama)",
    )
    parser = argparse.ArgumentParser(
        prog="research-assistant",
        description=(
            "Ingestion, retrieval, grounded generation, evaluation, and product API."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Ingest a local file", parents=[shared])
    ingest_p.add_argument("path", type=Path)
    ingest_p.add_argument(
        "--force",
        action="store_true",
        help="Re-parse even if checksum is unchanged",
    )

    show_p = sub.add_parser(
        "show", help="Print a stored document summary", parents=[shared]
    )
    show_p.add_argument("document_id")

    chunk_p = sub.add_parser(
        "chunk", help="Chunk a stored parsed document", parents=[shared]
    )
    chunk_p.add_argument("document_id")
    chunk_p.add_argument(
        "--strategy",
        choices=("structure", "window"),
        default="structure",
    )
    chunk_p.add_argument("--target-chars", type=int, default=None)
    chunk_p.add_argument("--max-chars", type=int, default=None)
    chunk_p.add_argument("--min-chars", type=int, default=None)
    chunk_p.add_argument("--overlap-chars", type=int, default=None)

    index_p = sub.add_parser(
        "index", help="Embed and index stored chunks", parents=[shared]
    )
    index_p.add_argument("document_id", nargs="?")
    index_p.add_argument(
        "--all",
        action="store_true",
        help="Index every document for the given chunker_id",
    )
    index_p.add_argument("--chunker-id", default=None)

    search_p = sub.add_parser(
        "search", help="Dense, lexical, or hybrid search (first-stage)", parents=[shared]
    )
    _add_query_args(search_p, include_top_k=True)

    rerank_p = sub.add_parser(
        "rerank", help="Hybrid candidates plus cross-encoder rerank", parents=[shared]
    )
    _add_query_args(rerank_p, include_top_k=False)
    rerank_p.add_argument(
        "--candidate-k",
        type=int,
        default=None,
        help="First-stage candidate pool size (default: rerank_candidate_k)",
    )
    rerank_p.add_argument(
        "--rerank-top-k",
        type=int,
        default=None,
        help="Reranked hits to keep (default: rerank_top_k)",
    )

    context_p = sub.add_parser(
        "context", help="Build citation-aware evidence context", parents=[shared]
    )
    _add_query_args(context_p, include_top_k=False)
    context_p.add_argument(
        "--candidate-k",
        type=int,
        default=None,
        help="First-stage candidate pool size",
    )
    context_p.add_argument(
        "--rerank-top-k",
        type=int,
        default=None,
        help="Reranked hits offered to the context builder",
    )
    context_p.add_argument(
        "--max-context-tokens",
        type=int,
        default=None,
        help="Approximate token budget for formatted evidence",
    )

    ask_p = sub.add_parser(
        "ask", help="Grounded answer from retrieved evidence", parents=[shared]
    )
    _add_query_args(ask_p, include_top_k=False)
    ask_p.add_argument(
        "--candidate-k",
        type=int,
        default=None,
        help="First-stage candidate pool size",
    )
    ask_p.add_argument(
        "--rerank-top-k",
        type=int,
        default=None,
        help="Reranked hits offered to the context builder",
    )
    ask_p.add_argument(
        "--max-context-tokens",
        type=int,
        default=None,
        help="Approximate token budget for formatted evidence",
    )
    ask_p.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print machine-readable JSON instead of the human layout",
    )

    eval_p = sub.add_parser(
        "evaluate", help="Run retrieval/generation evaluation", parents=[shared]
    )
    eval_p.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluation/datasets/ragbench_v1.jsonl"),
    )
    eval_p.add_argument(
        "--corpus",
        type=Path,
        default=Path("evaluation/corpus"),
    )
    eval_p.add_argument(
        "--stage",
        choices=("retrieval", "rerank", "context", "generation", "full"),
        default="retrieval",
    )
    eval_p.add_argument(
        "--mode",
        choices=("dense", "lexical", "hybrid"),
        default="hybrid",
    )
    eval_p.add_argument(
        "--split",
        choices=("dev", "test", "all"),
        default="test",
    )
    eval_p.add_argument(
        "--output",
        type=Path,
        default=Path("evaluation/results"),
    )
    eval_p.add_argument(
        "--prepare",
        action="store_true",
        help="Ingest, chunk, and index the corpus before evaluating",
    )
    eval_p.add_argument(
        "--chunk-strategy",
        choices=("structure", "window"),
        default="structure",
    )
    eval_p.add_argument("--candidate-k", type=int, default=None)
    eval_p.add_argument("--rerank-top-k", type=int, default=None)
    eval_p.add_argument("--max-context-tokens", type=int, default=None)
    eval_p.add_argument("--cache-dir", type=Path, default=None)
    eval_p.add_argument(
        "--workspace", type=Path, default=None,
        help="Isolated evaluation storage (default: evaluation/workspaces/<dataset-stem>)",
    )
    eval_p.add_argument(
        "--judge",
        action="store_true",
        help="Run the optional LLM judge (same provider unless tests inject a client)",
    )
    eval_p.add_argument(
        "--disable-rerank",
        action="store_true",
        help="Evaluation-only: collect evidence with rerank disabled",
    )
    eval_p.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Evaluation-only: repeat each selected item (qualitybench stability)",
    )
    eval_p.add_argument(
        "--tag",
        default=None,
        help="Evaluation-only: keep examples whose tags include this value",
    )

    serve_p = sub.add_parser(
        "serve", help="Run the local product HTTP API", parents=[shared]
    )
    serve_p.add_argument("--host", default=None, help="Bind host (default: API_HOST or 127.0.0.1)")
    serve_p.add_argument("--port", type=int, default=None, help="Bind port (default: API_PORT or 8000)")
    serve_p.add_argument(
        "--reload",
        action="store_true",
        help="Reload on code changes (development only)",
    )

    args = parser.parse_args(argv)
    if args.command == "evaluate" and (args.db is not None or args.index_path is not None):
        return _print_error(EvaluationError(
            "evaluate does not accept --db or --index-path; use --workspace for isolated storage.",
            code="evaluation_storage_flags",
        ))
    llm_provider = None
    llm_model = getattr(args, "llm_model", None)
    if llm_model and llm_model.startswith("scripted"):
        llm_provider = "scripted"
    settings = load_settings(
        database_path=args.db,
        log_level=args.log_level,
        embedding_model_name=args.embedding_model,
        embedding_device=args.device,
        vector_index_path=args.index_path,
        default_top_k=getattr(args, "top_k", None),
        reranker_model_name=getattr(args, "reranker", None),
        reranker_device=args.device,
        rerank_enabled=False if getattr(args, "no_rerank", False) else None,
        rerank_candidate_k=getattr(args, "candidate_k", None),
        rerank_top_k=getattr(args, "rerank_top_k", None),
        max_context_tokens=getattr(args, "max_context_tokens", None),
        llm_provider=llm_provider,
        llm_model_name=llm_model,
        llm_base_url=getattr(args, "llm_base_url", None),
    )
    configure_logging(settings.log_level)
    if args.command == "serve":
        return _cmd_serve(args, settings)
    if args.command == "evaluate":
        return _cmd_evaluate(settings, args)
    app = create_application(settings)

    if args.command == "ingest":
        return _cmd_ingest(app.ingest, args.path, force=args.force)
    if args.command == "show":
        return _cmd_show(app.ingest, args.document_id)
    if args.command == "chunk":
        return _cmd_chunk(app, args)
    if args.command == "index":
        return _cmd_index(app, args)
    if args.command == "search":
        return _cmd_search(app.hybrid, args)
    if args.command == "rerank":
        return _cmd_rerank(app.evidence, args)
    if args.command == "context":
        return _cmd_context(app.evidence, args)
    if args.command == "ask":
        return _cmd_ask(app.rag, args)
    parser.error(f"unknown command {args.command}")
    return 2


def _cmd_serve(args, settings) -> int:
    import os

    os.environ["RESEARCH_ASSISTANT_DATABASE_PATH"] = str(settings.database_path)
    os.environ["RESEARCH_ASSISTANT_VECTOR_INDEX_PATH"] = str(settings.vector_index_path)
    os.environ["RESEARCH_ASSISTANT_UPLOAD_DIR"] = str(settings.upload_dir)
    os.environ["RESEARCH_ASSISTANT_MAX_FILE_BYTES"] = str(settings.max_file_bytes)
    os.environ["LOG_LEVEL"] = settings.log_level
    if args.embedding_model:
        os.environ["RESEARCH_ASSISTANT_EMBEDDING_MODEL"] = args.embedding_model
    if args.reranker:
        os.environ["RESEARCH_ASSISTANT_RERANKER_MODEL"] = args.reranker
    if getattr(args, "no_rerank", False):
        os.environ["RESEARCH_ASSISTANT_RERANK_ENABLED"] = "false"
    if args.llm_model:
        os.environ["RESEARCH_ASSISTANT_LLM_MODEL"] = args.llm_model
    if args.llm_base_url:
        os.environ["RESEARCH_ASSISTANT_LLM_BASE_URL"] = args.llm_base_url
    try:
        import uvicorn
    except ImportError:
        print(
            "uvicorn is required for `serve`. Install with: pip install -e '.[api]'",
            file=sys.stderr,
        )
        return 1
    host = args.host or settings.api_host
    port = args.port if args.port is not None else settings.api_port
    print(
        f"Research Assistant API → http://{host}:{port}/health  (ready: /ready)",
        file=sys.stderr,
    )
    uvicorn.run(
        "research_assistant.api.app:create_api",
        factory=True,
        host=host,
        port=port,
        reload=bool(args.reload),
    )
    return 0


def _cmd_ingest(service: IngestionService, path: Path, *, force: bool) -> int:
    result = service.ingest(path, force=force)
    payload = {
        "outcome": result.outcome.value,
        "source_path": result.source_path,
        "ok": result.ok,
        "error_type": result.error_type,
        "error_message": result.error_message,
        "vector_purge_status": result.vector_purge_status.value,
        "vector_purge_error": result.vector_purge_error,
        "warnings": list(result.warnings),
    }
    if result.document is not None:
        payload["document_id"] = result.document.document_id
        payload["checksum_sha256"] = result.document.checksum_sha256
        payload["content_type"] = result.document.content_type.value
        payload["parse_status"] = result.document.parse_status.value
        payload["parser_id"] = result.document.parser_id
        payload["warning_count"] = result.document.warning_count
        payload["page_count"] = result.document.page_count
        payload["block_count"] = (
            len(result.parsed.blocks) if result.parsed is not None else 0
        )
        parser_warnings = list(result.parsed.warnings) if result.parsed else []
        payload["warnings"] = parser_warnings + list(result.warnings)
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    if not result.ok:
        return 1
    return 0


def _cmd_show(service: IngestionService, document_id: str) -> int:
    record = service.get_document(document_id)
    if record is None:
        print(f"document not found: {document_id}", file=sys.stderr)
        return 1
    parsed = record.parsed_document()
    payload = {
        "document_id": record.document_id,
        "source_path": record.source_path,
        "filename": record.filename,
        "content_type": record.content_type.value,
        "checksum_sha256": record.checksum_sha256,
        "parse_status": record.parse_status.value,
        "parser_id": record.parser_id,
        "ingested_at": record.ingested_at,
        "updated_at": record.updated_at,
        "warning_count": record.warning_count,
        "page_count": record.page_count,
        "error_type": record.error_type,
        "error_message": record.error_message,
        "warnings": list(parsed.warnings) if parsed else [],
        "blocks": [block.to_dict() for block in parsed.blocks] if parsed else [],
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_chunk(app, args) -> int:
    target = args.target_chars if args.target_chars is not None else DEFAULT_TARGET_CHARS
    max_chars = args.max_chars if args.max_chars is not None else max(DEFAULT_MAX_CHARS, target)
    min_chars = args.min_chars if args.min_chars is not None else min(DEFAULT_MIN_CHARS, target)
    overlap = (
        args.overlap_chars
        if args.overlap_chars is not None
        else min(DEFAULT_OVERLAP_CHARS, max(target - 1, 0))
    )
    config = ChunkingConfig(
        strategy=args.strategy,
        target_chars=target,
        max_chars=max_chars,
        min_chars=min_chars,
        overlap_chars=overlap,
    )
    result = app.chunking.chunk_document(args.document_id, config)
    sizes = [chunk.char_count for chunk in result.chunks]
    payload = {
        "outcome": result.outcome.value,
        "ok": result.ok,
        "document_id": result.document_id,
        "chunker_id": result.chunker_id,
        "chunk_count": len(result.chunks),
        "char_count_min": min(sizes) if sizes else 0,
        "char_count_max": max(sizes) if sizes else 0,
        "error_type": result.error_type,
        "error_message": result.error_message,
        "chunks": [
            {
                "position": chunk.position,
                "char_count": chunk.char_count,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "section_path": list(chunk.section_path),
                "warnings": list(chunk.warnings),
                "text_preview": chunk.text[:80],
            }
            for chunk in result.chunks
        ],
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    if not result.ok:
        return 1
    return 0


def _cmd_index(app, args) -> int:
    chunker_id = args.chunker_id
    if args.all:
        if not chunker_id:
            print("--chunker-id is required with --all", file=sys.stderr)
            return 2
        result = app.indexing.index_chunker(chunker_id)
    else:
        if not args.document_id:
            print("document_id is required unless --all is set", file=sys.stderr)
            return 2
        if not chunker_id:
            chunks = app.store.list_chunks(args.document_id)
            ids = sorted({chunk.chunker_id for chunk in chunks})
            if len(ids) != 1:
                print(
                    "Pass --chunker-id; stored chunker ids: "
                    + (", ".join(ids) if ids else "(none)"),
                    file=sys.stderr,
                )
                return 2
            chunker_id = ids[0]
        result = app.indexing.index_document(args.document_id, chunker_id)
    payload = {
        "outcome": result.outcome.value,
        "ok": result.ok,
        "index_id": result.index_id,
        "chunker_id": result.chunker_id,
        "embedding_model_id": result.embedding_model_id,
        "indexed_count": result.indexed_count,
        "skipped_empty": result.skipped_empty,
        "warnings": list(result.warnings),
        "error_type": result.error_type,
        "error_message": result.error_message,
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    if not result.ok:
        return 1
    return 0


def _cmd_search(search: HybridSearchService, args) -> int:
    try:
        filters = _filters_from_args(args)
        result = search.search(
            args.query,
            chunker_id=args.chunker_id,
            mode=args.mode,
            top_k=args.top_k,
            filters=filters,
        )
    except RetrievalError as exc:
        payload = {
            "ok": False,
            "error_type": exc.code,
            "error_message": exc.message,
        }
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1
    payload = {
        "ok": True,
        "mode": result.mode,
        "index_id": result.diagnostics.dense_index_id,
        "lexical_index_id": result.diagnostics.lexical_index_id,
        "search_ms": round(result.search_ms, 2),
        "diagnostics": result.diagnostics.to_dict(),
        "hits": [
            {
                "rank": hit.rank,
                "score": round(hit.score, 6),
                "fused_score": None
                if hit.fused_score is None
                else round(hit.fused_score, 6),
                "dense_rank": hit.dense_rank,
                "lexical_rank": hit.lexical_rank,
                "dense_score": None
                if hit.dense_score is None
                else round(hit.dense_score, 4),
                "lexical_score": None
                if hit.lexical_score is None
                else round(hit.lexical_score, 4),
                "retriever": hit.retriever,
                "retrievers": list(hit.retrievers),
                "document_id": hit.document_id,
                "filename": hit.filename,
                "page_start": hit.page_start,
                "page_end": hit.page_end,
                "section_path": list(hit.section_path),
                "text_preview": hit.text[:160],
            }
            for hit in result.hits
        ],
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_rerank(pipeline: EvidencePipeline, args) -> int:
    try:
        result = pipeline.collect(
            args.query,
            chunker_id=args.chunker_id,
            mode=args.mode,
            filters=_filters_from_args(args),
            candidate_k=args.candidate_k,
            rerank_top_k=args.rerank_top_k,
        )
    except (RetrievalError, RerankError, ContextError) as exc:
        return _print_error(exc)
    payload = {
        "ok": True,
        "mode": result.search.mode,
        "reranker_id": result.rerank.diagnostics.reranker_id,
        "rerank_enabled": result.rerank.diagnostics.enabled,
        "search_ms": round(result.search.search_ms, 2),
        "rerank_ms": round(result.rerank.diagnostics.inference_ms, 2),
        "search_diagnostics": result.search.diagnostics.to_dict(),
        "rerank_diagnostics": result.rerank.diagnostics.to_dict(),
        "hits": [
            {
                "retrieval_rank": hit.rank,
                "rerank_rank": hit.rerank_rank,
                "score": round(hit.score, 6),
                "rerank_score": None
                if hit.rerank_score is None
                else round(hit.rerank_score, 6),
                "fused_score": None
                if hit.fused_score is None
                else round(hit.fused_score, 6),
                "dense_rank": hit.dense_rank,
                "lexical_rank": hit.lexical_rank,
                "retriever": hit.retriever,
                "retrievers": list(hit.retrievers),
                "document_id": hit.document_id,
                "chunk_id": hit.chunk_id,
                "filename": hit.filename,
                "page_start": hit.page_start,
                "page_end": hit.page_end,
                "section_path": list(hit.section_path),
                "text_preview": hit.text[:160],
            }
            for hit in result.rerank.hits
        ],
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_context(pipeline: EvidencePipeline, args) -> int:
    try:
        result = pipeline.collect(
            args.query,
            chunker_id=args.chunker_id,
            mode=args.mode,
            filters=_filters_from_args(args),
            candidate_k=args.candidate_k,
            rerank_top_k=args.rerank_top_k,
            max_context_tokens=args.max_context_tokens,
        )
    except (RetrievalError, RerankError, ContextError) as exc:
        return _print_error(exc)
    payload = {
        "ok": True,
        "mode": result.search.mode,
        "reranker_id": result.rerank.diagnostics.reranker_id,
        "rerank_enabled": result.rerank.diagnostics.enabled,
        "search_diagnostics": result.search.diagnostics.to_dict(),
        "rerank_diagnostics": result.rerank.diagnostics.to_dict(),
        "context_diagnostics": result.context.diagnostics.to_dict(),
        "citations": [item.source.to_dict() for item in result.context.items],
        "rendered_text": result.context.rendered_text,
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_ask(rag: RAGService, args) -> int:
    try:
        result = rag.answer(
            args.query,
            chunker_id=args.chunker_id,
            mode=args.mode,
            filters=_filters_from_args(args),
            candidate_k=args.candidate_k,
            rerank_top_k=args.rerank_top_k,
            max_context_tokens=args.max_context_tokens,
        )
    except (RetrievalError, RerankError, ContextError, GenerationError) as exc:
        return _print_error(exc)
    answer = result.answer
    if getattr(args, "as_json", False):
        json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0 if answer.ok else 1
    if not answer.ok:
        print(f"VALIDATION FAILED ({answer.validation_status.value})", file=sys.stderr)
        if answer.invalid_citation_ids:
            print(
                "invalid_ids: " + ", ".join(answer.invalid_citation_ids),
                file=sys.stderr,
            )
        if answer.answer_text:
            print("raw_answer:", file=sys.stderr)
            print(answer.answer_text, file=sys.stderr)
        payload = {
            "ok": False,
            "error_type": answer.validation_status.value,
            "error_message": "Generation output failed citation validation",
            "invalid_citation_ids": list(answer.invalid_citation_ids),
            "diagnostics": answer.diagnostics.to_dict(),
        }
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 1
    print("ANSWER")
    print(answer.answer_text.strip() or "(empty)")
    print()
    print("SOURCES")
    sources = render_sources(answer.citations)
    print(sources if sources else "(none)")
    print()
    print("DIAGNOSTICS")
    diag = answer.diagnostics
    print(
        f"validation_status={answer.validation_status.value} "
        f"insufficient_evidence={answer.insufficient_evidence} "
        f"llm_id={diag.llm_id} generation_ms={diag.generation_ms:.1f} "
        f"empty_context={diag.empty_context_short_circuit}"
    )
    return 0


def _cmd_evaluate(settings, args) -> int:
    from research_assistant.chunking.config import default_config
    from research_assistant.evaluation.dataset import load_dataset, validate_dataset
    from research_assistant.evaluation.runner import EvaluationRunner
    from research_assistant.evaluation.workspace import open_workspace, validate_runtime_path

    app = None
    try:
        dataset = load_dataset(args.dataset)
        validate_dataset(dataset, corpus_dir=args.corpus)
        config = default_config(strategy=args.chunk_strategy)
        output_dir = validate_runtime_path(args.output, settings, args.corpus)
        workspace = (args.workspace or Path("evaluation/workspaces") / dataset.dataset_id).expanduser().resolve()
        cache_dir = (args.cache_dir or workspace / "cache").expanduser().resolve()
        if not cache_dir.is_relative_to(workspace):
            raise EvaluationError("--cache-dir must be inside --workspace", code="unsafe_evaluation_path")
        app, metadata = open_workspace(
            settings, dataset, corpus=args.corpus, chunking=config,
            path=workspace, prepare=args.prepare,
        )
        chunker_id = config.chunker_id
        split = None if args.split == "all" else args.split
        if dataset.dataset_id.startswith("qualitybench"):
            from research_assistant.evaluation.quality_runner import QualityEvaluationRunner

            runner = QualityEvaluationRunner(app, dataset, chunker_id=chunker_id, run_metadata=metadata)
            report = runner.run(
                stage=args.stage,
                mode=args.mode,
                split=split,
                candidate_k=args.candidate_k,
                rerank_top_k=args.rerank_top_k,
                max_context_tokens=args.max_context_tokens,
                rerank_enabled=False if getattr(args, "disable_rerank", False) else None,
                repeat=int(getattr(args, "repeat", 1) or 1),
                tag=getattr(args, "tag", None),
                output_dir=output_dir,
            )
        else:
            judge = None
            if getattr(args, "judge", False):
                from research_assistant.generation.factory import llm_from_settings

                judge = llm_from_settings(app.settings)
            runner = EvaluationRunner(
                app,
                dataset,
                chunker_id=chunker_id,
                cache_dir=cache_dir,
                judge=judge,
                run_metadata=metadata,
            )
            report = runner.run(
                stage=args.stage,
                mode=args.mode,
                split=split,
                candidate_k=args.candidate_k,
                rerank_top_k=args.rerank_top_k,
                max_context_tokens=args.max_context_tokens,
                output_dir=output_dir,
            )
    except EvaluationError as exc:
        return _print_error(exc)
    except (RetrievalError, RerankError, ContextError, GenerationError) as exc:
        return _print_error(exc)
    finally:
        if app is not None:
            app.indexing.vector_store.close()
            app.store.close()
    summary = {
        "ok": True,
        "run_id": report["run_id"],
        "metrics_schema": report["metrics_schema"],
        "workspace": report["workspace"],
        "dataset_sha256": report["dataset_sha256"],
        "corpus_sha256": report["corpus_sha256"],
        "git_commit": report["git_commit"],
        "output_path": report.get("output_path"),
        "config": report["config"],
        "identities": report["identities"],
        "metrics": report["metrics"],
    }
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _print_error(
    exc: RetrievalError | RerankError | ContextError | GenerationError | EvaluationError,
) -> int:
    payload = {
        "ok": False,
        "error_type": exc.code,
        "error_message": exc.message,
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 1


def _add_query_args(parser: argparse.ArgumentParser, *, include_top_k: bool) -> None:
    parser.add_argument("query")
    parser.add_argument("--chunker-id", required=True)
    if include_top_k:
        parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument(
        "--mode",
        choices=("dense", "lexical", "hybrid"),
        default=RetrievalMode.HYBRID.value,
        help="Retrieval mode (default: hybrid)",
    )
    parser.add_argument(
        "--document-id",
        action="append",
        dest="document_ids",
        default=None,
        help="Filter to this document_id (repeatable)",
    )
    parser.add_argument(
        "--filename",
        action="append",
        dest="filenames",
        default=None,
        help="Filter to this exact filename (repeatable)",
    )
    parser.add_argument("--page", type=int, default=None, help="Page overlap filter")
    parser.add_argument(
        "--section",
        default=None,
        help="Section path prefix, slash-separated (e.g. Methods/Training)",
    )


def _filters_from_args(args) -> RetrievalFilter | None:
    section = ()
    if getattr(args, "section", None):
        section = tuple(part for part in args.section.split("/") if part)
    document_ids = tuple(args.document_ids or ())
    filenames = tuple(args.filenames or ())
    page = getattr(args, "page", None)
    if not document_ids and not filenames and page is None and not section:
        return None
    return RetrievalFilter(
        document_ids=document_ids,
        filenames=filenames,
        page=page,
        section_prefix=section,
    )


if __name__ == "__main__":
    raise SystemExit(main())
