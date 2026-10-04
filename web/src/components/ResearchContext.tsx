import type { DocumentScope } from "../documentScope";
import { scopePresentation } from "../scopePresentation";

type ResearchContextProps = {
  id: string;
  scope: DocumentScope;
  libraryCount: number;
  availableCount: number;
  saving: boolean;
  error: string | null;
  loading: boolean;
  onRetry: () => void;
};

export function ResearchContext({
  id,
  scope,
  libraryCount,
  availableCount,
  saving,
  error,
  loading,
  onRetry,
}: ResearchContextProps) {
  const presentation = scopePresentation(scope, libraryCount, availableCount);

  return (
    <section id={id} className={`research-context${error ? " has-error" : ""}`}
      aria-label="Next question document scope">
      {loading ? (
        <p className="research-context-line" role="status">Loading research…</p>
      ) : (
        <>
          <p className="research-context-line">
            <span>Next question</span>
            <span aria-hidden="true">·</span>
            <strong>{presentation.label}</strong>
            {presentation.detail ? <span>· {presentation.detail}</span> : null}
          </p>
          {saving ? (
            <p className="research-context-state" role="status" aria-live="polite">
              Saving selection…
            </p>
          ) : null}
          {presentation.warning ? (
            <p className="research-context-warning" role="status">{presentation.warning}</p>
          ) : null}
          {error ? (
            <div className="research-context-error" role="alert">
              <span><strong>Selection not saved.</strong> {error}</span>
              <button type="button" className="btn-link" onClick={onRetry}>Retry saving</button>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
