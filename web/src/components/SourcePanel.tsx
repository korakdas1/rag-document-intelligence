import { useEffect } from "react";
import type { SourceView } from "../api/types";

type SourcePanelProps = {
  sources: SourceView[];
  activeCitationId: string | null;
  knownDocumentIds?: ReadonlySet<string>;
  onSelect: (citationId: string) => void;
};

function pageLabel(source: SourceView): string | null {
  if (source.page_start === null) {
    return source.section_path.length ? source.section_path.join(" › ") : null;
  }
  const pages =
    source.page_end !== null && source.page_end !== source.page_start
      ? `Pages ${source.page_start}–${source.page_end}`
      : `Page ${source.page_start}`;
  if (source.section_path.length) {
    return `${pages} · ${source.section_path.join(" › ")}`;
  }
  return pages;
}

export function SourcePanel({
  sources,
  activeCitationId,
  knownDocumentIds,
  onSelect,
}: SourcePanelProps) {
  useEffect(() => {
    if (!activeCitationId) {
      return;
    }
    const node = document.getElementById(`source-${activeCitationId}`);
    if (!node) {
      return;
    }
    const reduceMotion =
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
    node.scrollIntoView({
      block: "nearest",
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }, [activeCitationId, sources]);

  return (
    <section className="source-panel" aria-label="Sources">
      <header className="pane-heading">
        <h2>Sources</h2>
        {sources.length ? <span className="muted">{sources.length}</span> : null}
      </header>
      <div className="pane-scroll">
        {sources.length === 0 ? (
          <p className="muted">Retrieved passages will appear here after a question.</p>
        ) : (
          <>
            <p className="hint">
              Cited sources were referenced in the answer. Retrieved sources were shown to the
              model but not cited.
            </p>
            <ul className="source-list">
              {sources.map((source) => {
                const active = source.citation_id === activeCitationId;
                const location = pageLabel(source);
                return (
                  <li key={source.citation_id}>
                    <button
                      type="button"
                      id={`source-${source.citation_id}`}
                      className={`source-card ${source.cited_by_model ? "cited" : "retrieved"}${active ? " active" : ""}`}
                      onClick={() => onSelect(source.citation_id)}
                      aria-current={active ? "true" : undefined}
                    >
                      <header>
                        <span className="source-id">[{source.citation_id}]</span>
                        <span className="source-tags">
                          {source.cited_by_model ? (
                            <span className="tag">Cited</span>
                          ) : (
                            <span className="tag tag-quiet">Retrieved</span>
                          )}
                          {knownDocumentIds && !knownDocumentIds.has(source.document_id) ? (
                            <span className="tag tag-quiet">Removed from library</span>
                          ) : null}
                        </span>
                      </header>
                      <span className="source-file" title={source.filename}>
                        {source.filename}
                      </span>
                      {location ? <p className="locator">{location}</p> : null}
                      <blockquote className="passage">{source.text}</blockquote>
                    </button>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
