"""Document list, detail, and upload. Uses IngestionService + chunk + index."""

from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile

from research_assistant.api.deps import get_library, request_id_of
from research_assistant.api.errors import ApiError, error_from_domain
from research_assistant.api.schemas import (
    DeleteDocumentResponse,
    DocumentDetail,
    DocumentListResponse,
    UploadResponse,
)
from research_assistant.api.upload import sanitize_filename, validate_upload_content_type
from research_assistant.core.errors import IngestionError
from research_assistant.core.logging import get_logger

router = APIRouter(tags=["documents"])
logger = get_logger("research_assistant.api.documents")


@router.get("/documents", response_model=DocumentListResponse, summary="List documents")
def list_documents(request: Request) -> DocumentListResponse:
    library = get_library(request)
    return DocumentListResponse(
        documents=library.list_documents(),
        chunker_id=library.chunker_id,
        request_id=request_id_of(request),
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetail,
    summary="Document details",
)
def get_document(document_id: str, request: Request) -> DocumentDetail:
    return get_library(request).get_document(document_id)


@router.post("/documents", response_model=UploadResponse, summary="Upload and index")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
) -> UploadResponse:
    library = get_library(request)
    filename = sanitize_filename(file.filename or "")
    validate_upload_content_type(filename, file.content_type)
    max_bytes = library.max_file_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        piece = await file.read(1024 * 1024)
        if not piece:
            break
        total += len(piece)
        if total > max_bytes:
            raise ApiError(
                code="too_large",
                message=f"File exceeds max size ({max_bytes} bytes).",
                status_code=413,
                request_id=request_id_of(request),
            )
        chunks.append(piece)
    data = b"".join(chunks)
    logger.info("upload_received filename=%s bytes=%s", filename, len(data))
    try:
        path = library.save_upload(filename, data)
        prepared = library.ingest_and_index(path)
    except IngestionError as exc:
        raise error_from_domain(exc, request_id=request_id_of(request)) from exc
    return UploadResponse(
        document=prepared.summary,
        outcome=prepared.outcome,
        warnings=list(prepared.warnings),
        request_id=request_id_of(request),
    )


@router.post(
    "/documents/{document_id}/reindex",
    response_model=UploadResponse,
    summary="Re-index from the stored source file",
)
def reindex_document(document_id: str, request: Request) -> UploadResponse:
    library = get_library(request)
    try:
        prepared = library.reindex_document(document_id)
    except IngestionError as exc:
        raise error_from_domain(exc, request_id=request_id_of(request)) from exc
    return UploadResponse(
        document=prepared.summary,
        outcome=prepared.outcome,
        warnings=list(prepared.warnings),
        request_id=request_id_of(request),
    )


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteDocumentResponse,
    summary="Remove a document from the library",
)
def delete_document(document_id: str, request: Request) -> DeleteDocumentResponse:
    result = get_library(request).delete_document(document_id)
    return DeleteDocumentResponse(
        document_id=result.document_id,
        deleted=result.deleted,
        already_absent=result.already_absent,
        vector_cleanup_status=result.vector_cleanup_status,
        request_id=request_id_of(request),
    )
