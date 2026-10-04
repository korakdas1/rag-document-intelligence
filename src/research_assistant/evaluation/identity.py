"""Run identity and config snapshot for evaluation artifacts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_assistant.core.errors import EvaluationError

METRICS_SCHEMA = "evidence-metrics.v2"


def corpus_files(directory: Path) -> list[Path]:
    """The same top-level document set consumed by corpus preparation."""
    if not directory.is_dir():
        raise EvaluationError(f"Corpus directory missing: {directory}", code="corpus_missing")
    files = sorted(
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".pdf"}
    )
    if not files:
        raise EvaluationError(f"No documents in {directory}", code="empty_corpus")
    return files


def corpus_fingerprint(directory: Path) -> str:
    entries = [
        [path.name, hashlib.sha256(path.read_bytes()).hexdigest()]
        for path in corpus_files(directory)
    ]
    return hashlib.sha256(json.dumps(entries, ensure_ascii=False).encode("utf-8")).hexdigest()


def report_metadata(dataset, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """File digest when loaded from JSONL; explicit canonical fallback for fixtures."""
    canonical = json.dumps([item.to_dict() for item in dataset.examples], sort_keys=True)
    return {
        **(metadata or {}),
        "metrics_schema": METRICS_SCHEMA,
        "dataset_sha256": dataset.source_sha256 or hashlib.sha256(canonical.encode()).hexdigest(),
        "dataset_hash_kind": "file_bytes" if dataset.source_sha256 else "canonical_examples_json",
        "corpus_sha256": (metadata or {}).get("corpus_sha256"),
        "workspace": (metadata or {}).get("workspace"),
    }


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def config_fingerprint(config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def make_run_id(config: dict[str, Any], *, stamp: str | None = None) -> str:
    return f"eval_{stamp or utc_stamp()}_{config_fingerprint(config)}"


def git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
