import { apiRequest } from "./client";
import type { AskRequest, AskResponse } from "./types";

export function askQuestion(request: AskRequest): Promise<AskResponse> {
  return apiRequest<AskResponse>("/api/ask", {
    method: "POST",
    body: JSON.stringify(request),
  });
}
