"""FastAPI application factory. Wires HTTP to create_application()."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from research_assistant.api.deps import request_id_of
from research_assistant.api.errors import ApiError, error_from_domain, public_message
from research_assistant.api.library import DocumentLibrary
from research_assistant.api.routes_ask import router as ask_router
from research_assistant.api.routes_documents import router as documents_router
from research_assistant.api.routes_health import router as health_router
from research_assistant.api.routes_sessions import router as sessions_router
from research_assistant.api.sessions import ResearchSessionService
from research_assistant.app import Application, create_application
from research_assistant.core.errors import IngestionError
from research_assistant.core.logging import configure_logging, get_logger
from research_assistant.core.request_context import reset_request_id, sanitize_request_id, set_request_id

logger = get_logger("research_assistant.api")


class RequestIdMiddleware:
    """ASGI middleware so exception handlers still run (unlike BaseHTTPMiddleware)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = sanitize_request_id(Headers(scope=scope).get("x-request-id"))
        request_id = incoming or uuid.uuid4().hex[:16]
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id
        token = set_request_id(request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["x-request-id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            reset_request_id(token)


def create_api(application: Application | None = None) -> FastAPI:
    """Build the product API. Pass a test Application to avoid real models."""

    @asynccontextmanager
    async def lifespan(api: FastAPI) -> AsyncIterator[None]:
        configure_logging(_startup_log_level(application))
        wired = application or create_application()
        configure_logging(wired.settings.log_level)
        api.state.application = wired
        api.state.library = DocumentLibrary(wired)
        api.state.sessions = ResearchSessionService(wired)
        logger.info(
            "api_started env=%s host_bind_via_uvicorn=true",
            wired.settings.app_env,
        )
        try:
            yield
        finally:
            closer = getattr(wired.store, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:  # noqa: BLE001
                    logger.exception("database_close_failed")
            closer = getattr(wired.indexing.vector_store, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:  # noqa: BLE001
                    logger.exception("vector_store_close_failed")
            logger.info("api_stopped")

    api = FastAPI(
        title="Research Assistant API",
        description=(
            "Product HTTP layer over the existing RAG pipeline. "
            "GET /health is process liveness. GET /ready reports dependencies."
        ),
        version="0.10.0",
        lifespan=lifespan,
    )
    if application is not None:
        api.state.application = application
        api.state.library = DocumentLibrary(application)
        api.state.sessions = ResearchSessionService(application)

    origins = list(
        (application.settings.cors_origins if application is not None else None)
        or _cors_from_env()
    )
    api.add_middleware(RequestIdMiddleware)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-Id"],
    )

    @api.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        rid = request_id_of(_request) or exc.request_id
        body = ApiError(
            code=exc.code,
            message=public_message(exc.code, exc.message),
            status_code=exc.status_code,
            request_id=rid,
            turn_id=exc.turn_id,
            session_id=exc.session_id,
        ).payload()
        logger.info("api_error code=%s status=%s", exc.code, exc.status_code)
        return JSONResponse(status_code=exc.status_code, content=body)

    @api.exception_handler(IngestionError)
    async def _ingest_error(request: Request, exc: IngestionError) -> JSONResponse:
        mapped = error_from_domain(exc, request_id=request_id_of(request))
        logger.info("api_error code=%s status=%s", mapped.code, mapped.status_code)
        return JSONResponse(status_code=mapped.status_code, content=mapped.payload())

    @api.exception_handler(RequestValidationError)
    async def _validation(request: Request, _exc: RequestValidationError) -> JSONResponse:
        body = ApiError(
            code="validation_error",
            message="Request validation failed.",
            status_code=422,
            request_id=request_id_of(request),
        ).payload()
        return JSONResponse(status_code=422, content=body)

    @api.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        rid = request_id_of(request)
        if exc.status_code == 404:
            mapped = ApiError(
                code="not_found",
                message="Not found.",
                status_code=404,
                request_id=rid,
            )
        else:
            mapped = ApiError(
                code="http_error",
                message="Request failed.",
                status_code=exc.status_code,
                request_id=rid,
            )
        return JSONResponse(status_code=mapped.status_code, content=mapped.payload())

    @api.exception_handler(sqlite3.OperationalError)
    async def _sqlite_locked(request: Request, exc: sqlite3.OperationalError) -> JSONResponse:
        rid = request_id_of(request)
        text = str(exc).lower()
        if "locked" in text or "busy" in text:
            mapped = ApiError(
                code="database_busy",
                message="The document store is busy. Retry shortly.",
                status_code=503,
                request_id=rid,
            )
            logger.warning("database_busy")
            return JSONResponse(status_code=503, content=mapped.payload())
        logger.exception("sqlite_operational_error")
        body = ApiError(
            code="database_error",
            message="The document store could not complete the request.",
            status_code=503,
            request_id=rid,
        ).payload()
        return JSONResponse(status_code=503, content=body)

    @api.exception_handler(sqlite3.DatabaseError)
    async def _sqlite_corrupt(request: Request, _exc: sqlite3.DatabaseError) -> JSONResponse:
        body = ApiError(
            code="database_corrupt",
            message="The document store cannot be read.",
            status_code=503,
            request_id=request_id_of(request),
        ).payload()
        logger.exception("database_corrupt")
        return JSONResponse(status_code=503, content=body)

    @api.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(
            exc,
            (
                StarletteHTTPException,
                ApiError,
                IngestionError,
                RequestValidationError,
                sqlite3.DatabaseError,
            ),
        ):
            raise exc
        rid = request_id_of(request)
        logger.exception("unhandled_error")
        body = ApiError(
            code="internal_error",
            message="An unexpected error occurred.",
            status_code=500,
            request_id=rid,
        ).payload()
        return JSONResponse(status_code=500, content=body)

    api.include_router(health_router)
    api.include_router(documents_router, prefix="/api")
    api.include_router(sessions_router, prefix="/api")
    api.include_router(ask_router, prefix="/api")

    dist = Path("web/dist")
    if dist.is_dir():
        api.mount("/", StaticFiles(directory=dist, html=True), name="ui")

    return api


def _startup_log_level(application: Application | None) -> str:
    if application is not None:
        return application.settings.log_level
    import os

    return os.environ.get("LOG_LEVEL") or "INFO"


def _cors_from_env() -> tuple[str, ...]:
    from research_assistant.core.settings import DEFAULT_CORS_ORIGINS, load_settings

    try:
        return load_settings().cors_origins
    except Exception:  # noqa: BLE001
        return DEFAULT_CORS_ORIGINS
