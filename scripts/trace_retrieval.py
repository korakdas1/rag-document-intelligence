#!/usr/bin/env python3
"""Trace one stored chunk through dense, BM25, RRF, rerank, and context."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from research_assistant.app import create_application
from research_assistant.core.settings import load_settings
from research_assistant.indexing.qdrant_store import qdrant_store_for
from research_assistant.retrieval.filters import RetrievalFilter
from research_assistant.retrieval.trace import RetrievalTrace, RetrievalTracer


def main() -> int:
    args = _parser().parse_args()
    source_db = args.database.expanduser().resolve()
    source_index = args.index_path.expanduser().resolve()
    with _runtime_paths(
        source_db,
        source_index,
        snapshot=not args.no_snapshot,
    ) as (database, index_path):
        settings = load_settings(
            database_path=database,
            vector_index_path=index_path,
        )
        app = create_application(settings)
        try:
            target = app.store.get_chunk(args.chunk_id)
            if target is None:
                raise SystemExit(f"chunk not found: {args.chunk_id}")
            if args.chunker_id and target.chunker_id != args.chunker_id:
                raise SystemExit(
                    "target chunker mismatch: "
                    f"{target.chunker_id} != {args.chunker_id}"
                )
            document = app.store.get_by_id(target.document_id)
            filters = (
                RetrievalFilter(document_ids=tuple(args.document_id))
                if args.document_id
                else None
            )
            tracer = RetrievalTracer(
                dense=app.search,
                lexical=app.lexical,
                hybrid=app.hybrid,
                reranker=app.reranker,
                context=app.context,
                settings=settings,
            )
            modes = (
                (False, True)
                if args.rerank == "both"
                else (args.rerank == "on",)
            )
            traces = [
                tracer.trace(
                    args.query,
                    target_chunk_id=target.chunk_id,
                    chunker_id=target.chunker_id,
                    filters=filters,
                    rerank_enabled=enabled,
                    candidate_k=args.candidate_k,
                    rerank_top_k=args.rerank_top_k,
                    max_context_tokens=args.max_context_tokens,
                )
                for enabled in modes
            ]
            payload = {
                "target": {
                    "chunk_id": target.chunk_id,
                    "document_id": target.document_id,
                    "filename": document.filename if document else "",
                    "position": target.position,
                    "page_start": target.page_start,
                    "page_end": target.page_end,
                    "chunker_id": target.chunker_id,
                    "char_count": target.char_count,
                    "approx_token_count": target.approx_token_count,
                    "text_preview": target.text[: args.preview_chars],
                },
                "traces": [item.to_dict() for item in traces],
            }
            rendered = (
                json.dumps(payload, indent=2, ensure_ascii=False)
                if args.json
                else _render_human(payload, traces)
            )
            print(rendered)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
        finally:
            qdrant_store_for(index_path).close()
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Trace a target chunk through retrieval. Uses a temporary storage "
            "snapshot by default so the local API may keep running."
        )
    )
    parser.add_argument("--query", required=True)
    parser.add_argument("--chunk-id", required=True)
    parser.add_argument("--chunker-id")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/processed/research_assistant.db"),
    )
    parser.add_argument(
        "--index-path",
        type=Path,
        default=Path("data/indexes/qdrant"),
    )
    parser.add_argument(
        "--document-id",
        action="append",
        default=[],
        help="Optional document filter; repeatable.",
    )
    parser.add_argument("--candidate-k", type=int)
    parser.add_argument("--rerank-top-k", type=int)
    parser.add_argument("--max-context-tokens", type=int)
    parser.add_argument(
        "--rerank",
        choices=("on", "off", "both"),
        default="both",
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="Open runtime storage directly; stop other local Qdrant clients first.",
    )
    parser.add_argument("--preview-chars", type=int, default=500)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


@contextmanager
def _runtime_paths(
    database: Path,
    index_path: Path,
    *,
    snapshot: bool,
) -> Iterator[tuple[Path, Path]]:
    if not snapshot:
        yield database, index_path
        return
    with tempfile.TemporaryDirectory(prefix="rag-retrieval-trace-") as raw:
        root = Path(raw)
        snapshot_db = root / database.name
        snapshot_index = root / "qdrant"
        shutil.copy2(database, snapshot_db)
        shutil.copytree(index_path, snapshot_index)
        yield snapshot_db, snapshot_index


def _render_human(
    payload: dict[str, object],
    traces: list[RetrievalTrace],
) -> str:
    target = payload["target"]
    assert isinstance(target, dict)
    lines = [
        f"Target chunk: {target['chunk_id']}",
        f"Document: {target['filename']} ({target['document_id']})",
        (
            f"Position/pages: {target['position']} / "
            f"{target['page_start']}–{target['page_end']}"
        ),
        f"Chunker: {target['chunker_id']}",
        f"Preview: {target['text_preview']}",
    ]
    for trace in traces:
        lines.extend(
            [
                "",
                f"Query: {trace.query}",
                f"Rerank: {'on' if trace.rerank_enabled else 'off'}",
                f"Dense rank/score: {_rank_score(trace.dense_rank, trace.dense_score)}",
                (
                    "BM25 rank/score: "
                    f"{_rank_score(trace.lexical_rank, trace.lexical_score)}"
                ),
                (
                    "Hybrid rank/score: "
                    f"{_rank_score(trace.hybrid_rank, trace.fused_score)}"
                ),
                (
                    "Rerank rank/score: "
                    f"{_rank_score(trace.rerank_rank, trace.rerank_score)}"
                ),
                (
                    "Context selected: "
                    f"{trace.selected_in_context} "
                    f"(position={trace.context_position}, "
                    f"tokens_before={trace.context_tokens_used_before}, "
                    f"candidate_tokens={trace.context_candidate_tokens}, "
                    f"budget={trace.context_budget})"
                ),
                f"Dropped reason: {trace.dropped_reason or 'none'}",
            ]
        )
    return "\n".join(lines)


def _rank_score(rank: int | None, score: float | None) -> str:
    if rank is None:
        return "not present"
    return f"{rank} / {score:.6f}" if score is not None else f"{rank} / —"


if __name__ == "__main__":
    raise SystemExit(main())
