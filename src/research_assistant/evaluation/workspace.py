"""Owned evaluation storage; never open the serving application for CLI evaluation."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from research_assistant.app import Application, create_application
from research_assistant.chunking.config import ChunkingConfig
from research_assistant.core.errors import EvaluationError
from research_assistant.core.settings import Settings
from research_assistant.evaluation.identity import corpus_fingerprint, report_metadata
from research_assistant.evaluation.models import EvaluationDataset
from research_assistant.evaluation.prepare import prepare_corpus


def _overlaps(a: Path, b: Path) -> bool:
    return a == b or a in b.parents or b in a.parents


def validate_runtime_path(path: Path, serving: Settings, corpus: Path) -> Path:
    resolved = path.expanduser().resolve()
    protected = (
        serving.database_path.expanduser().resolve(),
        serving.vector_index_path.expanduser().resolve(),
        serving.upload_dir.expanduser().resolve(),
        Path("data/processed").resolve(), Path("data/indexes").resolve(),
        Path("data/uploads").resolve(), corpus.resolve(),
    )
    if any(_overlaps(resolved, item) for item in protected):
        raise EvaluationError(
            f"Evaluation path overlaps serving storage or corpus: {resolved}. "
            "Choose a separate --workspace/--output.", code="unsafe_evaluation_path",
        )
    return resolved


def validate_workspace_paths(
    serving: Settings, *, corpus: Path, workspace: Path,
    cache_dir: Path | None, output_dir: Path,
) -> tuple[Path, Path, Path]:
    """Resolve all CLI paths before writes and reserve workspace runtime storage.

    Only cache/ may hold generation caches, and only results/ may hold reports
    inside the workspace. This keeps research_assistant.db, indexes/, uploads/,
    cache/ (for reports), workspace.json, and their ancestors/descendants reserved.
    Reports outside the workspace must not be ancestors of the workspace either.
    """
    root = validate_runtime_path(workspace, serving, corpus)
    cache = validate_runtime_path(cache_dir if cache_dir is not None else root / "cache", serving, corpus)
    output = validate_runtime_path(output_dir, serving, corpus)
    # Candidates are resolved, but the allowed subtrees stay anchored to root:
    # a symlink named cache/ or results/ must not grant access to runtime storage.
    if not cache.is_relative_to(root / "cache"):
        raise EvaluationError(
            f"--cache-dir must be {root / 'cache'} or a descendant; "
            f"other workspace runtime paths are reserved: {cache}",
            code="unsafe_evaluation_path",
        )
    if _overlaps(output, root) and not output.is_relative_to(root / "results"):
        raise EvaluationError(
            f"--output must be outside the workspace (and not its ancestor) or "
            f"within {root / 'results'}; workspace runtime paths are reserved: {output}",
            code="unsafe_evaluation_path",
        )
    return root, cache, output


def open_workspace(
    serving: Settings, dataset: EvaluationDataset, *, corpus: Path,
    chunking: ChunkingConfig, path: Path | None, prepare: bool,
) -> tuple[Application, dict[str, Any]]:
    root = validate_runtime_path(
        path or Path("evaluation/workspaces") / dataset.dataset_id, serving, corpus,
    )
    # Refuse path aliases before opening SQLite/Qdrant or writing any metadata.
    if root.exists() and (not root.is_dir() or any(p.is_symlink() for p in root.rglob("*"))):
        raise EvaluationError("Workspace must be a directory without symlinks", code="unsafe_evaluation_path")
    database = root / "research_assistant.db"
    if database.exists() and serving.database_path.exists() and database.samefile(serving.database_path):
        raise EvaluationError("Workspace aliases the serving database", code="unsafe_evaluation_path")
    manifest_path = root / "workspace.json"
    identity = {
        "workspace_schema": "evaluation-workspace.v1",
        "dataset_sha256": report_metadata(dataset)["dataset_sha256"],
        "corpus_sha256": corpus_fingerprint(corpus),
        "chunker_id": chunking.chunker_id,
        "embedding_model": serving.embedding_model_name,
        "embedding_normalize": serving.embedding_normalize,
    }
    manifest: dict[str, Any] = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise EvaluationError("Invalid workspace manifest", code="workspace_incompatible") from exc
        if not isinstance(manifest, dict) or manifest.get("identity") != identity:
            raise EvaluationError(
                "Workspace dataset, corpus, chunker, or embedding configuration changed. "
                "Choose a new --workspace; existing data is preserved.", code="workspace_incompatible",
            )
    elif root.exists() and any(root.iterdir()):
        raise EvaluationError("Non-empty directory is not an evaluation workspace", code="workspace_not_owned")
    if not prepare and (not manifest.get("prepared") or not database.is_file()):
        raise EvaluationError("Evaluation workspace is not prepared. Re-run with --prepare.", code="corpus_not_prepared")

    root.mkdir(parents=True, exist_ok=True)
    for name in ("uploads", "indexes", "cache"):
        (root / name).mkdir(exist_ok=True)
    settings = replace(
        serving, database_path=database, upload_dir=root / "uploads",
        vector_index_path=root / "indexes" / "qdrant",
    )
    if prepare:
        # An interrupted preparation must not be accepted as reusable state.
        manifest_path.write_text(json.dumps({"identity": identity, "prepared": False}) + "\n")
    app = create_application(settings)
    try:
        if prepare:
            prepared = prepare_corpus(app, corpus, chunking=chunking)
            manifest = {"identity": identity, "prepared": True, "state": prepared}
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        state = manifest.get("state") or {}
        documents = app.store.list_documents()
        health = app.indexing.health.inspect(chunking.chunker_id)
        if (
            len(documents) != state.get("document_count")
            or sorted(doc.document_id for doc in documents) != state.get("document_ids")
            or not health or not all(item.ready for item in health.values())
            or app.indexing.index_id_for_chunker(chunking.chunker_id) != state.get("index_id")
        ):
            raise EvaluationError(
                "Evaluation corpus/index is absent or incompatible. Re-run with --prepare.",
                code="corpus_not_prepared",
            )
    except Exception:
        app.indexing.vector_store.close()
        app.store.close()
        raise
    return app, {"workspace": str(root), "corpus_sha256": identity["corpus_sha256"]}
