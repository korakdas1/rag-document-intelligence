import { apiUrl } from "./config";
import type { ApiErrorBody } from "./types";
import { looksLikeResourceDump, sanitizeUploadError } from "../userErrors";

export class ApiClientError extends Error {
  readonly code: string;
  readonly requestId: string;
  readonly status: number;
  readonly turnId: string;
  readonly sessionId: string;

  constructor(
    code: string,
    message: string,
    status: number,
    requestId = "",
    identity?: { turnId?: string; sessionId?: string },
  ) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
    this.turnId = identity?.turnId ?? "";
    this.sessionId = identity?.sessionId ?? "";
  }
}

export function describeApiFailure(error: unknown, fallback: string): string {
  if (error instanceof ApiClientError) {
    if (error.code === "resource_exhausted" || looksLikeResourceDump(error.message)) {
      return sanitizeUploadError(error.message);
    }
    if (error.code === "internal_error") {
      return `${fallback} The server did not confirm the result.`;
    }
    if (error.code === "invalid_response") {
      return error.message;
    }
    return looksLikeResourceDump(error.message)
      ? sanitizeUploadError(error.message)
      : error.message || fallback;
  }
  if (error instanceof Error && error.message) {
    return looksLikeResourceDump(error.message)
      ? sanitizeUploadError(error.message)
      : error.message;
  }
  return fallback;
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...init, headers });
  } catch {
    throw new ApiClientError(
      "network_error",
      "Could not reach the API. Is the backend running?",
      0,
    );
  }
  const requestId = response.headers.get("x-request-id") ?? "";
  if (!response.ok) {
    let payload: ApiErrorBody | null = null;
    try {
      payload = (await response.json()) as ApiErrorBody;
    } catch {
      payload = null;
    }
    throw new ApiClientError(
      payload?.error.code ?? "http_error",
      payload?.error.message ?? response.statusText,
      response.status,
      payload?.error.request_id || requestId,
      {
        turnId: payload?.error.turn_id ?? "",
        sessionId: payload?.error.session_id ?? "",
      },
    );
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiClientError(
      "invalid_response",
      "The API returned an unreadable success response.",
      response.status,
      requestId,
    );
  }
}
