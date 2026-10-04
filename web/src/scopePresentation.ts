import type { DocumentScope } from "./documentScope";

export type ScopePresentation = Readonly<{
  label: string;
  detail: string | null;
  warning: string | null;
}>;

export function scopePresentation(
  scope: DocumentScope,
  libraryCount: number,
  availableCount: number,
): ScopePresentation {
  if (scope.mode === "all") {
    return {
      label: "All documents",
      detail: libraryCount === 0
        ? "Library empty"
        : `${libraryCount} in library`,
      warning: null,
    };
  }

  if (scope.mode === "none") {
    return { label: "No documents selected", detail: null, warning: null };
  }

  const selectedCount = scope.documentIds.length;
  const missingCount = Math.max(0, selectedCount - availableCount);
  if (missingCount > 0) {
    return {
      label: `${availableCount} available of ${selectedCount} selected`,
      detail: null,
      warning: `${missingCount} selected document${missingCount === 1 ? " is" : "s are"} unavailable.`,
    };
  }
  return {
    label: `${selectedCount} selected document${selectedCount === 1 ? "" : "s"}`,
    detail: null,
    warning: null,
  };
}
