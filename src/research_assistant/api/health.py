"""Cheap component checks. Do not load embedding or rerank models."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from research_assistant.api.schemas import ComponentHealth, LivenessResponse, ReadyResponse
from research_assistant.app import Application


def build_liveness(*, request_id: str = "") -> LivenessResponse:
    return LivenessResponse(
        status="ok",
        service="research-assistant",
        request_id=request_id,
    )


def build_readiness(application: Application, *, request_id: str = "") -> ReadyResponse:
    database = _sqlite_ready(application)
    vector_store = _qdrant_ready(application)
    llm_provider = _llm_ready(application)
    embedding = ComponentHealth(
        status="configured",
        detail=application.settings.embedding_model_name,
    )
    if database.status != "ok":
        overall = "not_ready"
    elif vector_store.status != "ok" or llm_provider.status != "ok":
        overall = "degraded"
    else:
        overall = "ready"
    return ReadyResponse(
        status=overall,
        database=database,
        vector_store=vector_store,
        llm_provider=llm_provider,
        embedding=embedding,
        request_id=request_id,
    )


def _sqlite_ready(application: Application) -> ComponentHealth:
    try:
        application.store.ping()
        return ComponentHealth(status="ok", detail="sqlite reachable")
    except Exception:  # noqa: BLE001
        return ComponentHealth(status="unavailable", detail="sqlite unreachable")


def _qdrant_ready(application: Application) -> ComponentHealth:
    try:
        store = application.indexing.vector_store
        if hasattr(store, "collection_exists"):
            store.collection_exists("_health_probe")
        return ComponentHealth(status="ok", detail="vector store reachable")
    except Exception:  # noqa: BLE001
        return ComponentHealth(status="unavailable", detail="vector store unreachable")


def _llm_ready(application: Application) -> ComponentHealth:
    settings = application.settings
    provider = settings.llm_provider.strip().lower()
    if provider in {"scripted", "fake"} or settings.llm_model_name.startswith("scripted"):
        return ComponentHealth(status="ok", detail="scripted test provider")
    url = f"{settings.llm_base_url.rstrip('/')}/models"
    request = urllib.request.Request(url, method="GET")
    timeout = min(max(settings.health_probe_timeout_seconds, 0.1), 5.0)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(4096)
        try:
            json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        return ComponentHealth(status="ok", detail=settings.llm_model_name)
    except Exception:  # noqa: BLE001
        return ComponentHealth(status="unavailable", detail="llm provider unreachable")
