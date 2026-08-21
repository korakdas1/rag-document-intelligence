"""Grounded QA endpoint. Calls RAGService; does not retrieve in this module."""

from __future__ import annotations

from fastapi import APIRouter, Request

from research_assistant.api.deps import get_application, get_library, get_sessions, request_id_of
from research_assistant.api.errors import ApiError, error_from_domain
from research_assistant.api.mapping import to_ask_response
from research_assistant.api.schemas import AskRequest, AskResponse
from research_assistant.conversation.models import ConversationTurn
from research_assistant.core.errors import (
    ContextError,
    GenerationError,
    RerankError,
    RetrievalError,
)
from research_assistant.core.logging import get_logger
from research_assistant.core.types import RetrievalMode
from research_assistant.retrieval.filters import RetrievalFilter

router = APIRouter(tags=["ask"])
logger = get_logger("research_assistant.api.ask")


@router.post("/ask", response_model=AskResponse, summary="Grounded question answering")
def ask(body: AskRequest, request: Request) -> AskResponse:
    question = (body.question or "").strip()
    if not question:
        raise ApiError(
            code="empty_query",
            message="Question is empty.",
            status_code=400,
            request_id=request_id_of(request),
        )
    library = get_library(request)
    application = get_application(request)
    max_chars = application.settings.max_question_chars
    if len(question) > max_chars:
        raise ApiError(
            code="question_too_long",
            message=f"Question exceeds max length ({max_chars} characters).",
            status_code=400,
            request_id=request_id_of(request),
        )
    chunker_id = library.chunker_id
    if not application.store.list_chunks_for_chunker(chunker_id):
        raise ApiError(
            code="no_ready_documents",
            message="No indexed documents are available. Add a PDF, Markdown, or text file first.",
            status_code=409,
            request_id=request_id_of(request),
        )
    filters = None
    if body.document_ids:
        known = {item.document_id for item in library.list_documents()}
        missing = [item for item in body.document_ids if item not in known]
        if missing:
            raise ApiError(
                code="not_found",
                message="One or more selected documents were not found.",
                status_code=404,
                request_id=request_id_of(request),
            )
        filters = RetrievalFilter(document_ids=tuple(body.document_ids))
    mode = body.retrieval_mode
    if mode not in {item.value for item in RetrievalMode}:
        raise ApiError(
            code="invalid_filter",
            message="retrieval_mode must be hybrid, dense, or lexical.",
            status_code=400,
            request_id=request_id_of(request),
        )
    history = tuple(
        ConversationTurn(
            question=item.question,
            answer=item.answer,
            grounding_status=item.grounding_status,
            sequence=index + 1,
        )
        for index, item in enumerate(body.conversation)
        if item.question.strip()
    )
    sessions = get_sessions(request)
    session_id = (body.session_id or "").strip() or None
    if session_id:
        sessions.ensure_exists(session_id)
        history = sessions.resolver_history(
            session_id, exclude_turn_id=body.replace_turn_id
        )
    logger.info(
        "ask_started mode=%s rerank=%s filtered=%s history=%s session=%s request_id=%s",
        mode,
        body.rerank,
        bool(filters),
        len(history),
        session_id or "-",
        request_id_of(request),
    )
    try:
        result = application.rag.answer(
            question,
            chunker_id=chunker_id,
            mode=mode,
            filters=filters,
            rerank_enabled=body.rerank,
            conversation=history,
        )
    except (RetrievalError, RerankError, ContextError, GenerationError) as exc:
        mapped = error_from_domain(exc, request_id=request_id_of(request))
        logger.info("ask_failed code=%s", mapped.code)
        if session_id:
            try:
                turn = sessions.persist_error(
                    session_id,
                    question=question,
                    message=mapped.message,
                    replace_turn_id=body.replace_turn_id,
                )
            except ApiError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("session_persist_failed session_id=%s", session_id)
            else:
                mapped = ApiError(
                    code=mapped.code,
                    message=mapped.message,
                    status_code=mapped.status_code,
                    request_id=mapped.request_id,
                    turn_id=turn.turn_id,
                    session_id=session_id,
                )
        raise mapped from exc
    response = to_ask_response(result, request_id=request_id_of(request))
    if session_id:
        try:
            response = sessions.persist_result(
                session_id,
                question=question,
                result=result,
                request_id=request_id_of(request),
                replace_turn_id=body.replace_turn_id,
            )
        except ApiError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("session_persist_failed session_id=%s", session_id)
            raise ApiError(
                code="session_persist_failed",
                message="The answer was produced but could not be saved to the session.",
                status_code=500,
                request_id=request_id_of(request),
            ) from exc
    logger.info(
        "ask_completed grounding=%s validation=%s",
        response.grounding_status,
        response.validation_status,
    )
    return response
