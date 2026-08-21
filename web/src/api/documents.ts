import { apiRequest } from "./client";
import type {
  DeleteDocumentResponse,
  DocumentDetail,
  DocumentListResponse,
  UploadResponse,
} from "./types";

export function listDocuments(): Promise<DocumentListResponse> {
  return apiRequest<DocumentListResponse>("/api/documents");
}

export function getDocument(documentId: string): Promise<DocumentDetail> {
  return apiRequest<DocumentDetail>(`/api/documents/${encodeURIComponent(documentId)}`);
}

export function uploadDocument(file: File): Promise<UploadResponse> {
  const body = new FormData();
  body.append("file", file);
  return apiRequest<UploadResponse>("/api/documents", { method: "POST", body });
}

export function reindexDocument(documentId: string): Promise<UploadResponse> {
  return apiRequest<UploadResponse>(
    `/api/documents/${encodeURIComponent(documentId)}/reindex`,
    { method: "POST" },
  );
}

export function deleteDocument(documentId: string): Promise<DeleteDocumentResponse> {
  return apiRequest<DeleteDocumentResponse>(
    `/api/documents/${encodeURIComponent(documentId)}`,
    { method: "DELETE" },
  );
}
