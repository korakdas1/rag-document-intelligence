"""Report local dependency readiness. Does not download or repair anything."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from research_assistant.core.errors import ConfigurationError, DatabaseError
from research_assistant.core.settings import load_settings
from research_assistant.storage.sqlite import SqliteDocumentStore


def main() -> int:
    print("Research Assistant environment check")
    print("Does not download models, start services, or modify data.\n")
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(f"CONFIG  FAIL  {exc.message}")
        return 1
    print(f"APP_ENV          {settings.app_env}")
    print(f"LOG_LEVEL        {settings.log_level}")
    print(f"API bind         {settings.api_host}:{settings.api_port}")
    print(f"database path    {settings.database_path}")
    print(f"upload dir       {settings.upload_dir}")
    print(f"vector index     {settings.vector_index_path}")
    print(f"LLM model        {settings.llm_model_name}")
    print(f"LLM base URL     {settings.llm_base_url}")
    print(f"embedding model  {settings.embedding_model_name}")
    print(f"reranker model   {settings.reranker_model_name}")
    print(f"max upload       {settings.max_file_bytes} bytes")
    print()

    db_ok = _check_database(settings.database_path, settings.sqlite_busy_timeout_ms)
    qdrant_ok = _check_qdrant(settings.vector_index_path)
    llm_ok, llm_detail = _check_llm(settings.llm_base_url, settings.llm_model_name)
    print(f"SQLite           {'OK' if db_ok else 'FAIL'}")
    print(f"Qdrant local     {'OK' if qdrant_ok else 'FAIL'}  ({settings.vector_index_path})")
    print(f"LLM provider     {'OK' if llm_ok else 'FAIL'}  {llm_detail}")
    print()
    print("Embedding/rerank weights are loaded on first use and may require Hugging Face access.")
    print("Ollama is not required to start the API. Ask needs a reachable provider + model.")
    if db_ok and qdrant_ok:
        print("\nLibrary/session APIs should work. Ask additionally needs the LLM provider.")
        return 0 if llm_ok else 2
    return 1


def _check_database(path: Path, busy_timeout_ms: int) -> bool:
    try:
        store = SqliteDocumentStore(path, busy_timeout_ms=busy_timeout_ms)
        store.ping()
        return True
    except (DatabaseError, OSError) as exc:
        print(f"  sqlite error: {exc}")
        return False


def _check_qdrant(path: Path) -> bool:
    try:
        from research_assistant.indexing.qdrant_store import qdrant_store_for

        store = qdrant_store_for(path)
        store.collection_exists("_health_probe")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  qdrant error: {exc}")
        return False


def _check_llm(base_url: str, model_name: str) -> tuple[bool, str]:
    url = f"{base_url.rstrip('/')}/models"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            raw = response.read(8192)
        payload = json.loads(raw.decode("utf-8"))
    except urllib.error.URLError as exc:
        return False, f"unreachable ({exc.reason})"
    except Exception as exc:  # noqa: BLE001
        return False, f"probe failed ({type(exc).__name__})"
    ids: list[str] = []
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                ids.append(item["id"])
    if model_name in ids or any(model_name in item for item in ids):
        return True, f"model {model_name} listed"
    if ids:
        return False, f"reachable, but {model_name} not in /models"
    return True, "reachable (model list empty or unparsed)"


if __name__ == "__main__":
    sys.exit(main())
