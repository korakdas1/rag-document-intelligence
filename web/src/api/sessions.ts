import { apiRequest } from "./client";
import type {
  DeleteSessionResponse,
  SessionDetail,
  SessionListResponse,
  SessionSummary,
} from "./types";

export function listSessions(): Promise<SessionListResponse> {
  return apiRequest<SessionListResponse>("/api/sessions");
}

export function getSession(sessionId: string): Promise<SessionDetail> {
  return apiRequest<SessionDetail>(`/api/sessions/${encodeURIComponent(sessionId)}`);
}

export function createSession(body?: {
  title?: string;
  all_documents?: boolean;
  selected_document_ids?: string[];
}): Promise<SessionSummary> {
  return apiRequest<SessionSummary>("/api/sessions", {
    method: "POST",
    body: JSON.stringify(body ?? {}),
  });
}

export function patchSession(
  sessionId: string,
  body: {
    title?: string;
    all_documents?: boolean;
    selected_document_ids?: string[];
  },
): Promise<SessionSummary> {
  return apiRequest<SessionSummary>(`/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function deleteSession(sessionId: string): Promise<DeleteSessionResponse> {
  return apiRequest<DeleteSessionResponse>(`/api/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
}
