export type DocumentScope = Readonly<{
  mode: "all" | "subset" | "none";
  documentIds: readonly string[];
}>;

export function documentScope(allDocuments: boolean, ids: readonly string[]): DocumentScope {
  const documentIds = allDocuments ? [] : [...new Set(ids)];
  return { mode: allDocuments ? "all" : documentIds.length ? "subset" : "none", documentIds };
}

export function scopePayload(scope: DocumentScope) {
  return {
    all_documents: scope.mode === "all",
    selected_document_ids: [...scope.documentIds],
  };
}

export function visibleSelection(scope: DocumentScope, knownIds: string[]): string[] {
  if (scope.mode === "all") return knownIds;
  const known = new Set(knownIds);
  return scope.documentIds.filter((id) => known.has(id));
}

type ScopeSave = {
  scope: DocumentScope;
  settled: Promise<string | null>;
  error: string | null;
};

/** Each session has an ordered queue; a failed latest save blocks Ask until corrected. */
export class ScopeSaveQueue {
  private saves = new Map<string, ScopeSave>();

  current(sessionId: string) {
    return this.saves.get(sessionId);
  }

  save(sessionId: string, scope: DocumentScope, persist: () => Promise<unknown>): ScopeSave {
    const previous = this.saves.get(sessionId)?.settled ?? Promise.resolve(null);
    const entry: ScopeSave = { scope, settled: Promise.resolve(null), error: null };
    entry.settled = previous.then(async () => {
      try {
        await persist();
        return null;
      } catch {
        entry.error = "Could not save document selection. Change the selection to retry before asking.";
        return entry.error;
      }
    });
    this.saves.set(sessionId, entry);
    return entry;
  }

  async wait(sessionId: string): Promise<void> {
    for (;;) {
      const entry = this.saves.get(sessionId);
      if (!entry) return;
      const error = await entry.settled;
      if (entry !== this.saves.get(sessionId)) continue;
      if (error) throw new Error(error);
      return;
    }
  }
}
