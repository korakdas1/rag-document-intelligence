"""Request-scoped accessors for the wired Application."""

from __future__ import annotations

from fastapi import Request

from research_assistant.api.library import DocumentLibrary
from research_assistant.api.sessions import ResearchSessionService
from research_assistant.app import Application


def get_application(request: Request) -> Application:
    return request.app.state.application


def get_library(request: Request) -> DocumentLibrary:
    existing = getattr(request.app.state, "library", None)
    if existing is not None:
        return existing
    library = DocumentLibrary(get_application(request))
    request.app.state.library = library
    return library


def get_sessions(request: Request) -> ResearchSessionService:
    existing = getattr(request.app.state, "sessions", None)
    if existing is not None:
        return existing
    sessions = ResearchSessionService(get_application(request))
    request.app.state.sessions = sessions
    return sessions


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "") or ""
