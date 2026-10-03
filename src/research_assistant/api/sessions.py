"""Research session lifecycle. History is persisted for display and rewrite only."""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from research_assistant.api.errors import ApiError
from research_assistant.api.mapping import to_ask_response
from research_assistant.api.scope import DocumentScope
from research_assistant.api.schemas import (
    AskResponse,
    CitationView,
    DiagnosticsView,
    SessionDetail,
    SessionSummary,
    SessionTurnView,
    SourceView,
)
from research_assistant.app import Application
from research_assistant.conversation.models import ConversationTurn
from research_assistant.core.logging import get_logger
from research_assistant.generation.rag import RAGResult
from research_assistant.storage.records import (
    DEFAULT_SESSION_TITLE,
    MAX_SESSION_TITLE_LENGTH,
    SessionRecord,
    SessionTurnRecord,
)

logger = get_logger("research_assistant.api.sessions")


class ResearchSessionService:
    def __init__(self, application: Application) -> None:
        self._app = application

    @property
    def conversation_window(self) -> int:
        return self._app.settings.conversation_window

    def create_session(
        self,
        *,
        title: str | None = None,
        all_documents: bool = True,
        selected_document_ids: list[str] | None = None,
    ) -> SessionSummary:
        session_id = uuid.uuid4().hex
        now = _utc_now()
        cleaned = normalize_title(title) if title else DEFAULT_SESSION_TITLE
        scope = self._validated_scope(all_documents, selected_document_ids or ())
        record = self._app.store.create_session(
            session_id,
            title=cleaned,
            created_at=now,
            all_documents=scope.all_documents,
            selected_document_ids=scope.document_ids,
        )
        logger.info("session_created session_id=%s", session_id)
        return to_session_summary(record)

    def list_sessions(self) -> list[SessionSummary]:
        return [to_session_summary(item) for item in self._app.store.list_sessions()]

    def get_session(self, session_id: str, *, known_document_ids: set[str]) -> SessionDetail:
        record = self._require(session_id)
        logger.info("session_loaded session_id=%s turns=%s", session_id, record.turn_count)
        turns = [to_session_turn_view(item) for item in self._app.store.list_turns(session_id)]
        scope = DocumentScope.from_selection(record.all_documents, record.selected_document_ids)
        missing = len(set(scope.document_ids) - known_document_ids)
        payload = to_session_summary(record).model_dump()
        payload.update(
            {
                "all_documents": record.all_documents,
                "selected_document_ids": list(scope.document_ids),
                "missing_selected_count": missing,
                "turns": turns,
            }
        )
        return SessionDetail(**payload)

    def patch_session(
        self,
        session_id: str,
        *,
        title: str | None = None,
        all_documents: bool | None = None,
        selected_document_ids: list[str] | None = None,
    ) -> SessionSummary:
        record = self._require(session_id)
        if title is None and all_documents is None and selected_document_ids is None:
            raise ApiError(
                code="invalid_title",
                message="No session fields to update.",
                status_code=400,
            )
        next_title = normalize_title(title) if title is not None else None
        scope = None
        if all_documents is not None or selected_document_ids is not None:
            scope = self._validated_scope(
                record.all_documents if all_documents is None else all_documents,
                record.selected_document_ids if selected_document_ids is None else selected_document_ids,
            )
        updated = self._app.store.update_session(
            session_id,
            title=next_title,
            all_documents=scope.all_documents if scope is not None else None,
            selected_document_ids=scope.document_ids if scope is not None else None,
            updated_at=_utc_now(),
        )
        assert updated is not None
        if title is not None:
            logger.info("session_renamed session_id=%s", session_id)
        return to_session_summary(updated)

    def rename_session(self, session_id: str, title: str) -> SessionSummary:
        return self.patch_session(session_id, title=title)

    def update_selection(
        self,
        session_id: str,
        *,
        all_documents: bool,
        selected_document_ids: list[str],
    ) -> SessionSummary:
        return self.patch_session(
            session_id,
            all_documents=all_documents,
            selected_document_ids=selected_document_ids,
        )

    def document_scope(self, session_id: str) -> DocumentScope:
        record = self._require(session_id)
        return DocumentScope.from_selection(record.all_documents, record.selected_document_ids)

    def _validated_scope(self, all_documents: bool, document_ids: Sequence[str]) -> DocumentScope:
        scope = DocumentScope.from_selection(all_documents, document_ids)
        if scope.document_ids:
            scope.validate_known({doc.document_id for doc in self._app.store.list_documents()})
        return scope

    def delete_session(self, session_id: str) -> bool:
        existed = self._app.store.get_session(session_id) is not None
        deleted = self._app.store.delete_session(session_id)
        if deleted:
            logger.info("session_deleted session_id=%s", session_id)
        return existed and deleted

    def resolver_history(
        self, session_id: str, *, exclude_turn_id: str | None = None
    ) -> tuple[ConversationTurn, ...]:
        turns = [
            item
            for item in self._app.store.list_turns(session_id)
            if item.turn_id != exclude_turn_id
            and item.grounding_status != "error"
            and item.answer.strip()
        ]
        window = self.conversation_window
        bounded = turns[-window:]
        return tuple(
            ConversationTurn(
                question=item.question,
                answer=item.answer,
                grounding_status=item.grounding_status,
                sequence=item.sequence,
            )
            for item in bounded
        )

    def persist_result(
        self,
        session_id: str,
        *,
        question: str,
        result: RAGResult,
        request_id: str,
        replace_turn_id: str | None = None,
    ) -> AskResponse:
        response = to_ask_response(result, request_id=request_id)
        turn = self._write_turn(
            session_id,
            question=question,
            answer=response.answer,
            grounding_status=response.grounding_status,
            validation_status=response.validation_status,
            insufficient_evidence=response.insufficient_evidence,
            error_message=None,
            original_question=response.diagnostics.original_question,
            retrieval_query=response.diagnostics.retrieval_query,
            generation_question=response.diagnostics.generation_question,
            sources_json=json.dumps(
                [item.model_dump() for item in response.sources], ensure_ascii=False
            ),
            citations_json=json.dumps(
                [item.model_dump() for item in response.citations], ensure_ascii=False
            ),
            diagnostics_json=json.dumps(response.diagnostics.model_dump(), ensure_ascii=False),
            replace_turn_id=replace_turn_id,
        )
        logger.info(
            "turn_persisted session_id=%s turn_id=%s status=%s",
            session_id,
            turn.turn_id,
            turn.grounding_status,
        )
        return response.model_copy(
            update={"session_id": session_id, "turn_id": turn.turn_id}
        )

    def persist_error(
        self,
        session_id: str,
        *,
        question: str,
        message: str,
        replace_turn_id: str | None = None,
    ) -> SessionTurnRecord:
        turn = self._write_turn(
            session_id,
            question=question,
            answer="",
            grounding_status="error",
            validation_status=None,
            insufficient_evidence=False,
            error_message=message,
            original_question=question,
            retrieval_query=None,
            generation_question=None,
            sources_json="[]",
            citations_json="[]",
            diagnostics_json=None,
            replace_turn_id=replace_turn_id,
        )
        logger.info(
            "turn_persisted session_id=%s turn_id=%s status=error",
            session_id,
            turn.turn_id,
        )
        return turn

    def _write_turn(
        self,
        session_id: str,
        *,
        question: str,
        answer: str,
        grounding_status: str,
        validation_status: str | None,
        insufficient_evidence: bool,
        error_message: str | None,
        original_question: str | None,
        retrieval_query: str | None,
        generation_question: str | None,
        sources_json: str,
        citations_json: str,
        diagnostics_json: str | None,
        replace_turn_id: str | None,
    ) -> SessionTurnRecord:
        session = self._require(session_id)
        now = _utc_now()
        existing = None
        if replace_turn_id:
            existing = self._app.store.get_turn(replace_turn_id)
            if existing is None or existing.session_id != session_id:
                raise ApiError(
                    code="not_found",
                    message="Turn not found.",
                    status_code=404,
                )
        else:
            latest = self._app.store.list_turns(session_id)
            trailing = latest[-1] if latest else None
            if (
                trailing is not None
                and trailing.grounding_status == "error"
                and trailing.question == question
            ):
                existing = trailing
        turn_id = existing.turn_id if existing else uuid.uuid4().hex
        sequence = existing.sequence if existing else self._app.store.next_turn_sequence(session_id)
        created_at = existing.created_at if existing else now
        record = SessionTurnRecord(
            turn_id=turn_id,
            session_id=session_id,
            sequence=sequence,
            question=question,
            original_question=original_question,
            retrieval_query=retrieval_query,
            generation_question=generation_question,
            answer=answer,
            grounding_status=grounding_status,
            validation_status=validation_status,
            insufficient_evidence=insufficient_evidence,
            error_message=error_message,
            sources_json=sources_json,
            citations_json=citations_json,
            diagnostics_json=diagnostics_json,
            created_at=created_at,
        )
        self._app.store.upsert_turn(record, session_updated_at=now)
        if session.turn_count == 0 and session.title == DEFAULT_SESSION_TITLE:
            derived = title_from_question(question)
            self._app.store.update_session(session_id, title=derived, updated_at=now)
        return record

    def ensure_exists(self, session_id: str) -> None:
        self._require(session_id)

    def _require(self, session_id: str) -> SessionRecord:
        record = self._app.store.get_session(session_id)
        if record is None:
            raise ApiError(
                code="not_found",
                message="Research session not found.",
                status_code=404,
            )
        return record


def normalize_title(title: str) -> str:
    cleaned = " ".join((title or "").split())
    if not cleaned:
        raise ApiError(
            code="invalid_title",
            message="Session title cannot be empty.",
            status_code=400,
        )
    if len(cleaned) > MAX_SESSION_TITLE_LENGTH:
        cleaned = cleaned[: MAX_SESSION_TITLE_LENGTH - 3].rstrip() + "..."
    return cleaned


def title_from_question(question: str) -> str:
    try:
        return normalize_title(question)
    except ApiError:
        return DEFAULT_SESSION_TITLE


def to_session_summary(record: SessionRecord) -> SessionSummary:
    return SessionSummary(
        session_id=record.session_id,
        title=record.title,
        created_at=record.created_at,
        updated_at=record.updated_at,
        turn_count=record.turn_count,
        all_documents=record.all_documents,
    )


def to_session_turn_view(record: SessionTurnRecord) -> SessionTurnView:
    sources = [SourceView.model_validate(item) for item in json.loads(record.sources_json or "[]")]
    citations = [
        CitationView.model_validate(item) for item in json.loads(record.citations_json or "[]")
    ]
    diagnostics = None
    if record.diagnostics_json:
        diagnostics = DiagnosticsView.model_validate(json.loads(record.diagnostics_json))
    return SessionTurnView(
        turn_id=record.turn_id,
        sequence=record.sequence,
        question=record.question,
        answer=record.answer,
        grounding_status=record.grounding_status,
        validation_status=record.validation_status,
        insufficient_evidence=record.insufficient_evidence,
        error_message=record.error_message,
        original_question=record.original_question,
        retrieval_query=record.retrieval_query,
        generation_question=record.generation_question,
        citations=citations,
        sources=sources,
        diagnostics=diagnostics,
        created_at=record.created_at,
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
