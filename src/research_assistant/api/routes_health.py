"""Liveness and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from research_assistant.api.deps import get_application, request_id_of
from research_assistant.api.health import build_liveness, build_readiness
from research_assistant.api.schemas import LivenessResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=LivenessResponse, summary="Process liveness")
@router.get("/api/health", response_model=LivenessResponse, include_in_schema=False)
def health(request: Request) -> LivenessResponse:
    """API process is alive. Does not probe SQLite, Qdrant, Ollama, or models."""
    return build_liveness(request_id=request_id_of(request))


@router.get("/ready", response_model=ReadyResponse, summary="Dependency readiness")
@router.get("/api/ready", response_model=ReadyResponse, include_in_schema=False)
def ready(request: Request) -> ReadyResponse:
    """Bounded dependency probes. Does not download or run embedding models."""
    return build_readiness(get_application(request), request_id=request_id_of(request))
