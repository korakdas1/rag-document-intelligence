"""Optional generation cache. Keyed by llm_id + question + context identity, not question alone."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def context_identity(rendered_text: str, citation_ids: tuple[str, ...]) -> str:
    payload = json.dumps(
        {"citations": list(citation_ids), "text": rendered_text},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cache_key(llm_id: str, question: str, context_id: str) -> str:
    payload = json.dumps(
        {"llm_id": llm_id, "question": question, "context_id": context_id},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GenerationCache:
    def __init__(self, directory: Path | None) -> None:
        self._directory = directory
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path(key)
        if path is None or not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, key: str, payload: dict[str, Any]) -> None:
        path = self._path(key)
        if path is None:
            return
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _path(self, key: str) -> Path | None:
        if self._directory is None:
            return None
        return self._directory / f"{key}.json"
