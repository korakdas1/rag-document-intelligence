import { apiRequest } from "./client";
import type { HealthResponse, ReadyResponse } from "./types";

export function getHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("/api/health");
}

export function getReady(): Promise<ReadyResponse> {
  return apiRequest<ReadyResponse>("/api/ready");
}
