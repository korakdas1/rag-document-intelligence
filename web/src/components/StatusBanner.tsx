import type { ReadyResponse } from "../api/types";

type StatusBannerProps = {
  ready: ReadyResponse | null;
  healthError: string | null;
};

export function StatusBanner({ ready, healthError }: StatusBannerProps) {
  if (healthError) {
    return (
      <div className="banner banner-warn" role="status">
        Cannot reach the API. Start it with{" "}
        <code>python -m research_assistant serve</code>.
      </div>
    );
  }
  if (!ready) {
    return null;
  }
  if (ready.status === "not_ready") {
    return (
      <div className="banner banner-warn" role="status">
        The document store is not ready. Library and ask requests may fail.
      </div>
    );
  }
  if (ready.llm_provider.status !== "ok") {
    return (
      <div className="banner banner-warn" role="status">
        Language model unavailable. Document search and indexing may still work.
      </div>
    );
  }
  if (ready.status === "degraded") {
    return (
      <div className="banner banner-warn" role="status">
        Some services are degraded
        {ready.vector_store.status !== "ok" ? " (vector index)" : ""}
        {ready.database.status !== "ok" ? " (document store)" : ""}.
      </div>
    );
  }
  return null;
}
