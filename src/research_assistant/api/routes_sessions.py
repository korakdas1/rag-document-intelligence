"""Persistent research sessions. Does not retrieve or generate."""

from __future__ import annotations

from fastapi import APIRouter, Request

from research_assistant.api.deps import get_application, get_sessions, request_id_of
from research_assistant.api.schemas import (
    CreateSessionRequest,
    DeleteSessionResponse,
    PatchSessionRequest,
    SessionDetail,
    SessionListResponse,
    SessionSummary,
)

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionSummary, summary="Create a research session")
def create_session(body: CreateSessionRequest, request: Request) -> SessionSummary:
    return get_sessions(request).create_session(
        title=body.title,
        all_documents=body.all_documents,
        selected_document_ids=body.selected_document_ids,
    )


@router.get("/sessions", response_model=SessionListResponse, summary="List research sessions")
def list_sessions(request: Request) -> SessionListResponse:
    return SessionListResponse(
        sessions=get_sessions(request).list_sessions(),
        request_id=request_id_of(request),
    )


@router.get("/sessions/{session_id}", response_model=SessionDetail, summary="Load a session")
def get_session(session_id: str, request: Request) -> SessionDetail:
    known = {item.document_id for item in get_application(request).store.list_documents()}
    return get_sessions(request).get_session(session_id, known_document_ids=known)


@router.patch("/sessions/{session_id}", response_model=SessionSummary, summary="Update a session")
def patch_session(
    session_id: str, body: PatchSessionRequest, request: Request
) -> SessionSummary:
    return get_sessions(request).patch_session(
        session_id,
        title=body.title,
        all_documents=body.all_documents,
        selected_document_ids=body.selected_document_ids,
    )


@router.delete(
    "/sessions/{session_id}",
    response_model=DeleteSessionResponse,
    summary="Delete a research session",
)
def delete_session(session_id: str, request: Request) -> DeleteSessionResponse:
    deleted = get_sessions(request).delete_session(session_id)
    return DeleteSessionResponse(
        session_id=session_id,
        deleted=True,
        already_absent=not deleted,
        request_id=request_id_of(request),
    )
