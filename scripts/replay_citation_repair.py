"""One frozen 13-case DEV citation-repair replay; never retrieves or generates answers.

Requires the authoritative saved v5 report and its original isolated SQLite metadata.
The report preserves evidence excerpts/IDs/order, but not source header fields. Only
those saved chunk IDs are read from SQLite (immutable/read-only) to restore headers.
No chunk selection, context budgeting, question rewriting or first-pass call occurs.
An output directory must not exist: a completed/partial run is never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
from datetime import datetime, timezone
import urllib.request

from research_assistant.context.format import render_bundle, render_evidence_block
from research_assistant.context.models import CitationSource, ContextBundle, ContextDiagnostics, ContextItem
from research_assistant.generation.citations import extract_citations
from research_assistant.generation.openai_compatible import OpenAICompatibleClient
from research_assistant.generation.prompt import PROMPT_VERSION, REPAIR_PROMPT_VERSION, build_repair_request
from research_assistant.generation.repair import preserves_answer_content, validate_citation_repair
from research_assistant.retrieval.models import RetrievalHit

SOURCE_RUN = "eval_20261004T092610Z_7e617cae80ec"
SOURCE_SHA = "befd206e7ff5b6d18f2e7672710a4f2f59b434ff5ca11482b778bf6e2bde2aa1"
MODEL_DIGEST = "dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364"
POPULATION = (
    "qb2-004", "qb2-005", "qb2-025", "qb2-027", "qb2-029", "qb2-049", "qb2-050",
    "qb2-051", "qb2-052", "qb2-053", "qb2-075", "qb2-076", "qb2-077",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source(path: Path) -> tuple[dict, list[dict]]:
    if sha256(path) != SOURCE_SHA:
        raise ValueError("Source raw report SHA does not match the frozen DEV report")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report["run_id"] != SOURCE_RUN or report["config"]["split"] != "dev":
        raise ValueError("Only the authoritative DEV report is permitted")
    rows = [row for row in report["examples"]
            if row["first_pass_validation_status"] == "missing_citations"
            and row["repair_attempts"] == 1]
    if tuple(row["example_id"] for row in rows) != POPULATION:
        raise ValueError("Frozen 13-case repair population does not match")
    if any(row["split"] != "dev" for row in rows):
        raise ValueError("Replay includes a non-DEV row")
    return report, rows


def saved_bundle(row: dict, connection: sqlite3.Connection) -> ContextBundle:
    """Restore headers only; keep raw-report evidence bytes, order and IDs intact."""
    items, rendered = [], []
    for position, block in enumerate(row["context_blocks"], 1):
        record = connection.execute(
            "SELECT c.*, d.filename FROM chunks c JOIN documents d "
            "ON c.document_id = d.document_id WHERE c.chunk_id = ?",
            (block["chunk_id"],),
        ).fetchone()
        if record is None:
            raise ValueError("Saved evidence metadata is unavailable")
        if record["document_id"] != block["document_id"] or record["filename"] != block["filename"]:
            raise ValueError("Saved evidence provenance differs from original workspace")
        if ((not block["truncated"] and record["text"] != block["text"])
                or (block["truncated"] and not record["text"].startswith(block["text"]))):
            raise ValueError("Saved evidence excerpt differs from original workspace")
        source = CitationSource(
            citation_id=block["citation_id"], chunk_id=block["chunk_id"],
            document_id=block["document_id"], filename=block["filename"],
            page_start=record["page_start"], page_end=record["page_end"],
            section_path=tuple(json.loads(record["section_path"])),
            content_hash=record["content_hash"], chunker_id=record["chunker_id"],
        )
        item = ContextItem(
            citation_id=block["citation_id"], text=block["text"], truncated=block["truncated"],
            rank=position, rerank_score=None, retrieval_rank=position, source=source,
        )
        items.append(item)
        hit = RetrievalHit(
            chunk_id=source.chunk_id, document_id=source.document_id, rank=position,
            score=0.0, retriever="saved_evidence", text=item.text,
            page_start=source.page_start, page_end=source.page_end, section_path=source.section_path,
            chunker_id=source.chunker_id, index_id="", embedding_model_id="",
            filename=source.filename, content_hash=source.content_hash,
        )
        rendered.append(render_evidence_block(item.citation_id, hit, item.text))
    allowed = tuple(item.citation_id for item in items)
    if allowed != tuple(row["context_citation_ids"]):
        raise ValueError("Saved allowed citation IDs differ from evidence order")
    diagnostics = ContextDiagnostics(
        input_count=len(items), selected_count=len(items), skipped_count=0, duplicate_count=0,
        redundant_count=0, truncated_count=sum(item.truncated for item in items),
        skipped_budget_count=0, max_context_tokens=1024, estimated_tokens=0,
        accounting="saved_evidence_replay", citation_ids=allowed,
        source_document_count=len({item.source.document_id for item in items}), skipped_chunk_ids=(),
    )
    return ContextBundle(query="", items=tuple(items), rendered_text=render_bundle(rendered), diagnostics=diagnostics)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New, non-existing run directory")
    args = parser.parse_args()
    report, rows = load_source(args.source)
    if PROMPT_VERSION != "grounded.answerability.v5":
        raise ValueError("First-pass prompt must remain v5")
    # Only this isolated source workspace is read; no serving paths are opened.
    database = Path(report["workspace"]) / "research_assistant.db"
    database_sha = sha256(database)
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        bundles = [saved_bundle(row, connection) for row in rows]
    finally:
        connection.close()
    client = OpenAICompatibleClient(
        model_name="qwen2.5-coder:7b", base_url="http://127.0.0.1:11434/v1",
        temperature=0.0, max_output_tokens=512, timeout_seconds=120.0,
        response_format="json_object", keep_alive="",
    )
    if client.identity.llm_id != report["identities"]["llm_id"]:
        raise ValueError("Replay model configuration differs from source")
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as response:
        tags = json.load(response)
    model = next(item for item in tags["models"] if item["name"] == client.identity.model_name)
    if model["digest"] != MODEL_DIGEST:
        raise ValueError("Replay model digest differs from source")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "diff", "HEAD", "--", "src", "scripts/replay_citation_repair.py"], text=True):
        raise ValueError("Commit the candidate implementation before live calls")
    args.output.mkdir(parents=True, exist_ok=False)
    now = datetime.now(timezone.utc)
    record = {
        "run_id": f"repair_{now:%Y%m%dT%H%M%SZ}_{commit[:12]}",
        "started_at": now.isoformat(), "status": "running", "implementation_commit": commit,
        "source_run": SOURCE_RUN, "source_sha256": SOURCE_SHA,
        "source_workspace_database_sha256": database_sha,
        "population": list(POPULATION), "model": client.identity.to_dict(),
        "model_digest": model["digest"], "first_pass_prompt": PROMPT_VERSION,
        "repair_prompt": REPAIR_PROMPT_VERSION,
        "live_first_pass_calls": 0, "retrieval_calls": 0, "third_calls": 0,
        "repair_calls_started": 0, "examples": [],
    }
    write_json(args.output / "run.json", record)
    try:
        for row, bundle in zip(rows, bundles, strict=True):
            original = row["first_pass_answer_text"]
            request = build_repair_request(bundle, client.identity, original)
            record["repair_calls_started"] += 1
            write_json(args.output / "run.json", record)
            response = client.generate(request)  # Exactly one live call per saved row; no retries.
            # Preserve raw response before validation, including any rejected content.
            case = {"example_id": row["example_id"], "original_answer": original,
                    "request": request.to_dict(), "response": response.to_dict()}
            write_json(args.output / f"{row['example_id']}.json", case)
            validation = validate_citation_repair(original, response.text, bundle)
            case.update({
                "repaired_answer": validation.parsed.answer,
                "accepted": validation.accepted, "rejection_reason": validation.rejection_reason,
                "content_preserved": validation.content_preserved,
                "produced_citation_ids": list(extract_citations(validation.parsed.answer).ids),
                "insufficient_evidence": validation.parsed.insufficient_evidence,
                "final_answer": validation.parsed.answer if validation.accepted else original,
                "final_status": "valid" if validation.accepted else "missing_citations",
                "historical_repaired_answer": row["answer_text"],
                "historical_strict_content_preserved": preserves_answer_content(
                    original, row["answer_text"], request.allowed_citation_ids),
                "historical_repair_drift": row["repair_drift"],
                "historical_repair_ms": row["timings_ms"]["repair_ms"],
                "evidence_sha256": hashlib.sha256(bundle.rendered_text.encode()).hexdigest(),
            })
            record["examples"].append(case)
            write_json(args.output / "run.json", record)
            print(row["example_id"], "accepted" if validation.accepted else validation.rejection_reason,
                  f"{response.generation_ms:.2f} ms", flush=True)
        if sha256(args.source) != SOURCE_SHA or sha256(database) != database_sha:
            raise ValueError("Source artifacts changed during replay")
        record["status"] = "completed"
        record["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        write_json(args.output / "run.json", record)
    print(record["run_id"], "completed", flush=True)


if __name__ == "__main__":
    main()
