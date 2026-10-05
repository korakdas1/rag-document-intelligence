import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { WorkspaceLayout, type WorkspacePane } from "./components/WorkspaceLayout";
import { Dialog } from "./components/ui/Dialog";
import { documentScope, scopePayload, ScopeSaveQueue, visibleSelection } from "./documentScope";
import type { DocumentScope } from "./documentScope";
import { askQuestion } from "./api/ask";
import { ApiClientError, describeApiFailure } from "./api/client";
import {
  deleteDocument,
  getDocument,
  listDocuments,
  reindexDocument,
  uploadDocument,
} from "./api/documents";
import { getHealth, getReady } from "./api/health";
import {
  createSession,
  deleteSession,
  getSession,
  listSessions,
  patchSession,
} from "./api/sessions";
import type {
  AskResponse,
  DocumentDetail,
  DocumentSummary,
  GroundingStatus,
  ReadyResponse,
  RetrievalMode,
  SessionDetail,
  SessionSummary,
  SessionTurnView,
} from "./api/types";
import { ConversationEmpty } from "./components/ConversationEmpty";
import { ConversationErrorBoundary } from "./components/ConversationErrorBoundary";
import { ConversationTurn } from "./components/ConversationTurn";
import { DeleteDocumentDialog } from "./components/DeleteDocumentDialog";
import { DeleteSessionDialog } from "./components/DeleteSessionDialog";
import { DiagnosticsPanel } from "./components/DiagnosticsPanel";
import { DocumentDetails } from "./components/DocumentDetails";
import { DocumentSidebar } from "./components/DocumentSidebar";
import { QuestionInput } from "./components/QuestionInput";
import { ResearchContext } from "./components/ResearchContext";
import { RenameSessionDialog } from "./components/RenameSessionDialog";
import { SessionSwitcher } from "./components/SessionSwitcher";
import { SourcePanel } from "./components/SourcePanel";
import { StatusBanner } from "./components/StatusBanner";
import type { UploadFailure, UploadFeedbackState } from "./components/UploadFeedback";
import { scrollPaneToTurn, spacerHeightToPinTurn } from "./conversationScroll";
import { resolveDroppedFiles, UNSUPPORTED_UPLOAD_MESSAGE } from "./uploadAccept";
import { sanitizeUploadError } from "./userErrors";
import { useFileDrop } from "./useFileDrop";

type Turn = {
  id: string;
  question: string;
  response: AskResponse | null;
  error: string | null;
  retryable?: boolean;
};

const CONVERSATION_WINDOW = 4;
const REINDEX_VISIBLE_MS = 400;
const UPLOAD_FEEDBACK_MS = 7000;

function waitForPaint(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(() => resolve());
      return;
    }
    setTimeout(resolve, 0);
  });
}

async function keepBusyVisible(startedAt: number): Promise<void> {
  const remaining = REINDEX_VISIBLE_MS - (Date.now() - startedAt);
  if (remaining > 0) {
    await new Promise((resolve) => {
      setTimeout(resolve, remaining);
    });
  }
}

function completedHistory(turns: Turn[]): {
  question: string;
  answer: string;
  grounding_status: string;
}[] {
  return turns
    .filter((turn) => turn.response)
    .slice(-CONVERSATION_WINDOW)
    .map((turn) => ({
      question: turn.question,
      answer: turn.response?.answer ?? "",
      grounding_status: turn.response?.grounding_status ?? "",
    }));
}

function newTurnId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `turn-${Date.now()}`;
}

function isClientTurnId(id: string): boolean {
  return id.includes("-") || id.startsWith("turn-");
}

function sessionTurnResponse(item: SessionTurnView): AskResponse {
  return {
    question: item.question,
    answer: item.answer,
    grounding_status: item.grounding_status as GroundingStatus,
    validation_status: item.validation_status ?? "",
    insufficient_evidence: Boolean(item.insufficient_evidence),
    citations: item.citations,
    sources: item.sources,
    diagnostics: item.diagnostics ?? {
      retrieval_mode: "hybrid",
      rerank_enabled: true,
      candidate_count: 0,
      context_source_count: item.sources.length,
      dense_ms: null,
      lexical_ms: null,
      fusion_ms: null,
      retrieval_ms: null,
      rerank_ms: null,
      generation_ms: null,
      llm_id: null,
      reranker_id: null,
      validation_status: item.validation_status ?? "",
      candidates: [],
      original_question: item.original_question,
      retrieval_query: item.retrieval_query,
      generation_question: item.generation_question,
    },
    request_id: "",
    session_id: null,
    turn_id: item.turn_id,
  };
}

function turnsFromSession(detail: SessionDetail): Turn[] {
  return detail.turns.map((item) => {
    const failed =
      item.grounding_status === "error" || Boolean(item.error_message && !item.answer);
    return {
      id: item.turn_id,
      question: item.question,
      response: failed ? null : sessionTurnResponse(item),
      error: failed ? item.error_message ?? null : null,
      retryable: true,
    };
  });
}

export default function App() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [activeTurnId, setActiveTurnId] = useState<string | null>(null);
  const [activeCitationId, setActiveCitationId] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFeedback, setUploadFeedback] = useState<UploadFeedbackState | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [mode, setMode] = useState<RetrievalMode>("hybrid");
  const [rerank, setRerank] = useState(true);
  const [pane, setPane] = useState<WorkspacePane>("workspace");
  const [filter, setFilter] = useState("");
  const [busyDocumentId, setBusyDocumentId] = useState<string | null>(null);
  const [busyKind, setBusyKind] = useState<"reindex" | "delete" | null>(null);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [documentActionError, setDocumentActionError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<DocumentSummary | null>(null);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [libraryChanged, setLibraryChanged] = useState(false);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeTitle, setActiveTitle] = useState("New research");
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [scopeError, setScopeError] = useState<string | null>(null);
  const [scopeSaving, setScopeSaving] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [pendingRename, setPendingRename] = useState<SessionSummary | null>(null);
  const [pendingSessionDelete, setPendingSessionDelete] = useState<SessionSummary | null>(null);
  const [sessionBusy, setSessionBusy] = useState(false);
  const activeSessionIdRef = useRef<string | null>(null);
  const askingRef = useRef(false);
  const questionRef = useRef("");
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const turnsRef = useRef<Turn[]>([]);
  const selectedIdsRef = useRef<string[]>([]);
  const documentsRef = useRef<DocumentSummary[]>([]);
  const scopeRef = useRef(documentScope(true, []));
  const scopeSavesRef = useRef(new ScopeSaveQueue());
  const sessionLoadRef = useRef(0);
  const sessionLoadingRef = useRef(false);
  const pinBehaviorRef = useRef<ScrollBehavior>("auto");
  const uploadInFlightRef = useRef(false);
  const uploadGenerationRef = useRef(0);
  const busyDocumentIdRef = useRef<string | null>(null);
  const conversationScrollRef = useRef<HTMLDivElement>(null);
  const followSpaceRef = useRef<HTMLDivElement>(null);
  const turnNodesRef = useRef(new Map<string, HTMLLIElement>());
  const pinTurnIdRef = useRef<string | null>(null);
  const followTurnIdRef = useRef<string | null>(null);
  const programmaticScrollRef = useRef(false);
  const lastScrollTopRef = useRef(0);
  const pinPassRef = useRef(0);
  const [pinSpace, setPinSpace] = useState(0);
  const questionContextId = useId();

  const activeTurn =
    turns.find((turn) => turn.id === activeTurnId) ?? turns[turns.length - 1] ?? null;
  const sources = activeTurn?.response?.sources ?? [];
  const knownDocumentIds = new Set(documents.map((item) => item.document_id));
  const canAsk = selectedIds.length > 0;
  turnsRef.current = turns;
  selectedIdsRef.current = selectedIds;
  documentsRef.current = documents;
  questionRef.current = question;

  function bindTurnNode(turnId: string) {
    return (node: HTMLLIElement | null) => {
      if (node) {
        turnNodesRef.current.set(turnId, node);
      } else {
        turnNodesRef.current.delete(turnId);
      }
    };
  }

  function stopFollowing() {
    pinTurnIdRef.current = null;
    followTurnIdRef.current = null;
  }

  function pinTurnNow(turnId: string, behavior: ScrollBehavior = "auto") {
    pinTurnIdRef.current = turnId;
    followTurnIdRef.current = turnId;
    pinBehaviorRef.current = behavior;
    pinPassRef.current = 0;
  }

  function setComposerValue(text: string) {
    questionRef.current = text;
    setQuestion(text);
  }

  function onConversationScroll() {
    const pane = conversationScrollRef.current;
    if (!pane) {
      return;
    }
    const top = pane.scrollTop;
    if (programmaticScrollRef.current) {
      lastScrollTopRef.current = top;
      return;
    }
    if (followTurnIdRef.current && askingRef.current && top + 2 < lastScrollTopRef.current) {
      followTurnIdRef.current = null;
    }
    lastScrollTopRef.current = top;
  }

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (uploading || uploadFeedback?.kind !== "result" || uploadFeedback.failures.length > 0) {
      return;
    }
    const handle = window.setTimeout(() => {
      setUploadFeedback(null);
    }, UPLOAD_FEEDBACK_MS);
    return () => window.clearTimeout(handle);
  }, [uploadFeedback, uploading]);

  useLayoutEffect(() => {
    const turnId = pinTurnIdRef.current;
    if (!turnId) {
      return;
    }
    const pane = conversationScrollRef.current;
    const turn = turnNodesRef.current.get(turnId);
    if (!pane || !turn) {
      return;
    }
    pinPassRef.current += 1;
    if (pinPassRef.current > 4) {
      programmaticScrollRef.current = true;
      scrollPaneToTurn(pane, turn, { behavior: pinBehaviorRef.current });
      pinTurnIdRef.current = null;
      pinPassRef.current = 0;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          programmaticScrollRef.current = false;
        });
      });
      return;
    }
    const nextSpace = spacerHeightToPinTurn(pane, turn, pinSpace);
    if (nextSpace !== pinSpace) {
      setPinSpace(nextSpace);
      return;
    }
    programmaticScrollRef.current = true;
    scrollPaneToTurn(pane, turn, { behavior: pinBehaviorRef.current });
    pinTurnIdRef.current = null;
    pinPassRef.current = 0;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        programmaticScrollRef.current = false;
      });
    });
  }, [turns, pinSpace]);

  async function bootstrap() {
    await refreshDocuments();
    await refreshHealth();
    await restoreLatestSession();
  }

  async function refreshHealth() {
    try {
      await getHealth();
      setHealthError(null);
    } catch (error) {
      setReady(null);
      setHealthError(error instanceof Error ? error.message : "health failed");
      return;
    }
    try {
      setReady(await getReady());
    } catch {
      setReady(null);
    }
  }

  async function refreshDocuments(): Promise<boolean> {
    try {
      const listed = await listDocuments();
      documentsRef.current = listed.documents;
      setDocuments(listed.documents);
      const allIds = listed.documents.map((item) => item.document_id);
      applyScope(scopeRef.current, allIds);
      setLibraryError(null);
      return true;
    } catch (error) {
      const message =
        error instanceof ApiClientError ? error.message : "Could not load the document library.";
      setLibraryError(message);
      return false;
    }
  }

  async function refreshSessionList() {
    try {
      const listed = await listSessions();
      setSessions(listed.sessions);
      return listed.sessions;
    } catch (error) {
      const message =
        error instanceof ApiClientError ? error.message : "Could not load research sessions.";
      setSessionError(message);
      return null;
    }
  }

  async function restoreLatestSession() {
    const listed = await refreshSessionList();
    if (!listed) {
      return;
    }
    const latest = listed.find((item) => item.turn_count > 0);
    if (latest) {
      await openSession(latest.session_id);
    }
  }

  async function openSession(sessionId: string) {
    const generation = ++sessionLoadRef.current;
    sessionLoadingRef.current = true;
    setSessionLoading(true);
    setSessionError(null);
    try {
      // Keep any failed local intent visible on return; Ask still requires its save.
      await scopeSavesRef.current.wait(sessionId).catch(() => undefined);
      const saveAtLoad = scopeSavesRef.current.current(sessionId);
      const loaded = await getSession(sessionId);
      if (generation !== sessionLoadRef.current) return;
      const latestSave = scopeSavesRef.current.current(sessionId);
      applySession(loaded, latestSave !== saveAtLoad || Boolean(latestSave?.error));
    } catch (error) {
      if (generation !== sessionLoadRef.current) return;
      const message =
        error instanceof ApiClientError ? error.message : "Could not load the conversation.";
      setSessionError(message);
    } finally {
      if (generation === sessionLoadRef.current) {
        sessionLoadingRef.current = false;
        setSessionLoading(false);
      }
    }
  }

  function applySession(loaded: SessionDetail, useLocalScope = false) {
    stopFollowing();
    setPinSpace(0);
    setActiveSessionId(loaded.session_id);
    activeSessionIdRef.current = loaded.session_id;
    setActiveTitle(loaded.title);
    const nextTurns = turnsFromSession(loaded);
    setTurns(nextTurns);
    setActiveTurnId(nextTurns.at(-1)?.id ?? null);
    setActiveCitationId(null);
    const pending = scopeSavesRef.current.current(loaded.session_id);
    applyScope(
      useLocalScope && pending
        ? pending.scope
        : documentScope(loaded.all_documents, loaded.selected_document_ids),
    );
    setScopeError(pending?.error ?? null);
    setScopeSaving(Boolean(pending?.pending));
    setLibraryChanged(false);
  }

  function startNewConversation() {
    ++sessionLoadRef.current;
    sessionLoadingRef.current = false;
    setSessionLoading(false);
    stopFollowing();
    setPinSpace(0);
    setTurns([]);
    setActiveTurnId(null);
    setActiveCitationId(null);
    setLibraryChanged(false);
    setActiveSessionId(null);
    activeSessionIdRef.current = null;
    setActiveTitle("New research");
    setSessionError(null);
    setScopeError(null);
    setScopeSaving(false);
    applyScope(documentScope(true, []));
  }

  function applyScope(
    scope: DocumentScope,
    knownIds = documentsRef.current.map((doc) => doc.document_id),
  ) {
    scopeRef.current = scope;
    const visible = visibleSelection(scope, knownIds);
    selectedIdsRef.current = visible;
    setSelectedIds(visible);
  }

  function persistSelection(scope: DocumentScope) {
    const sessionId = activeSessionIdRef.current;
    if (!sessionId) return;
    const payload = scopePayload(scope);
    const entry = scopeSavesRef.current.save(sessionId, scope, () =>
      patchSession(sessionId, payload),
    );
    if (
      activeSessionIdRef.current === sessionId &&
      scopeSavesRef.current.current(sessionId) === entry
    ) {
      setScopeSaving(true);
      setScopeError(null);
    }
    void entry.settled.then((error) => {
      if (
        activeSessionIdRef.current === sessionId &&
        scopeSavesRef.current.current(sessionId) === entry
      ) {
        setScopeSaving(false);
        setScopeError(error);
      }
    });
  }

  function changeScope(scope: DocumentScope) {
    applyScope(scope);
    setScopeError(null);
    setScopeSaving(false);
    persistSelection(scope);
  }

  function retryScopeSave() {
    persistSelection(scopeRef.current);
  }

  function selectAllDocuments() {
    changeScope(documentScope(true, []));
  }

  function clearDocumentSelection() {
    changeScope(documentScope(false, []));
  }

  function toggleDocument(documentId: string) {
    const current = selectedIdsRef.current;
    const next = current.includes(documentId)
      ? current.filter((id) => id !== documentId)
      : [...current, documentId];
    changeScope(documentScope(false, next));
  }

  async function handleUploadFiles(files: File[]) {
    if (uploadInFlightRef.current) {
      return;
    }
    const resolved = resolveDroppedFiles(files);
    if (resolved.accepted.length === 0) {
      const failures: UploadFailure[] = resolved.rejected.length > 0
        ? resolved.rejected
        : [{ filename: "Files", reason: resolved.error ?? UNSUPPORTED_UPLOAD_MESSAGE }];
      setUploadFeedback({ kind: "result", added: 0, failures });
      return;
    }
    uploadInFlightRef.current = true;
    const generation = ++uploadGenerationRef.current;
    const failures: UploadFailure[] = [...resolved.rejected];
    const succeeded: { id: string; document: DocumentSummary }[] = [];
    setUploading(true);
    setUploadFeedback({ kind: "progress", current: 1, total: resolved.accepted.length });
    try {
      for (let index = 0; index < resolved.accepted.length; index += 1) {
        if (generation !== uploadGenerationRef.current) {
          return;
        }
        const file = resolved.accepted[index];
        setUploadFeedback({
          kind: "progress",
          current: index + 1,
          total: resolved.accepted.length,
        });
        try {
          const uploaded = await uploadDocument(file);
          succeeded.push({
            id: uploaded.document.document_id,
            document: uploaded.document,
          });
        } catch (error) {
          if (generation !== uploadGenerationRef.current) {
            return;
          }
          const recovered = await findUploadedByFilename(file.name);
          if (recovered) {
            succeeded.push({ id: recovered.document_id, document: recovered });
            continue;
          }
          failures.push({
            filename: file.name || "file",
            reason: sanitizeUploadError(
              describeApiFailure(error, "Upload failed."),
              file.name,
            ),
            retryFile: file,
          });
        }
      }
      if (generation !== uploadGenerationRef.current) {
        return;
      }
      const succeededIds = succeeded.map((item) => item.id);
      if (succeeded.length > 0) {
        const refreshed = await refreshDocuments();
        if (generation !== uploadGenerationRef.current) {
          return;
        }
        noteLibraryChange();
        if (scopeRef.current.mode === "all") {
          setSelectedIds((current) => {
            const next = [...current];
            for (const id of succeededIds) {
              if (!next.includes(id)) {
                next.push(id);
              }
            }
            return next;
          });
        }
        if (!refreshed) {
          setDocuments((current) => {
            const next = [...current];
            for (const item of succeeded) {
              if (!next.some((doc) => doc.document_id === item.id)) {
                next.push(item.document);
              }
            }
            return next;
          });
          setLibraryError(
            "Document uploaded, but the library could not be refreshed. Retry loading the library.",
          );
        }
      }
      if (generation !== uploadGenerationRef.current) {
        return;
      }
      setUploadFeedback({ kind: "result", added: succeeded.length, failures });
    } finally {
      if (generation === uploadGenerationRef.current) {
        setUploading(false);
        uploadInFlightRef.current = false;
      }
    }
  }

  async function findUploadedByFilename(filename: string): Promise<DocumentSummary | null> {
    try {
      const listed = await listDocuments();
      return listed.documents.find((item) => item.filename === filename) ?? null;
    } catch {
      return null;
    }
  }

  function ingestDroppedFiles(files: File[]) {
    if (uploading || busyDocumentId || uploadInFlightRef.current) {
      return;
    }
    void handleUploadFiles(files);
  }

  async function ensureSession(): Promise<string> {
    if (activeSessionIdRef.current) {
      return activeSessionIdRef.current;
    }
    const initialScope = scopeRef.current;
    const created = await createSession(scopePayload(initialScope));
    setActiveSessionId(created.session_id);
    activeSessionIdRef.current = created.session_id;
    setActiveTitle(created.title);
    if (scopeRef.current !== initialScope) persistSelection(scopeRef.current);
    await refreshSessionList();
    return created.session_id;
  }

  async function requestAnswer(text: string, replaceTurnId?: string) {
    if (
      !text || askingRef.current || sessionLoadingRef.current || selectedIdsRef.current.length === 0
    ) {
      return;
    }
    askingRef.current = true;
    setAsking(true);
    const id = replaceTurnId ?? newTurnId();
    const historySource = turnsRef.current;
    if (replaceTurnId) {
      setTurns((current) =>
        current.map((turn) =>
          turn.id === id
            ? { ...turn, response: null, error: null, retryable: true }
            : turn,
        ),
      );
    } else {
      const pending: Turn = {
        id,
        question: text,
        response: null,
        error: null,
        retryable: true,
      };
      setTurns((current) => [...current, pending]);
      setComposerValue("");
    }
    setActiveTurnId(id);
    setActiveCitationId(null);
    pinTurnNow(id, "smooth");
    try {
      const sessionId = await ensureSession();
      await scopeSavesRef.current.wait(sessionId);
      if (scopeRef.current.mode === "none" || selectedIdsRef.current.length === 0) {
        throw new Error("Select at least one document before asking a question.");
      }
      const history = replaceTurnId
        ? completedHistory(historySource.filter((turn) => turn.id !== id))
        : completedHistory(historySource);
      const persistedReplace =
        replaceTurnId && !isClientTurnId(replaceTurnId) ? replaceTurnId : undefined;
      const response = await askQuestion({
        question: text,
        retrieval_mode: mode,
        rerank,
        conversation: history,
        session_id: sessionId,
        replace_turn_id: persistedReplace,
      });
      const persistedId = response.turn_id ?? id;
      if (followTurnIdRef.current === id) {
        followTurnIdRef.current = persistedId;
      }
      if (pinTurnIdRef.current === id) {
        pinTurnIdRef.current = persistedId;
      }
      setTurns((current) =>
        current.map((turn) =>
          turn.id === id
            ? { ...turn, id: persistedId, response, error: null, retryable: true }
            : turn,
        ),
      );
      setActiveTurnId(persistedId);
      const firstCited = response.citations[0]?.citation_id;
      const firstSource = response.sources[0]?.citation_id;
      setActiveCitationId(firstCited ?? firstSource ?? null);
      setPane("workspace");
      const listed = await refreshSessionList();
      const current = listed?.find((item) => item.session_id === sessionId);
      if (current) {
        setActiveTitle(current.title);
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "The request failed.";
      const persistedId =
        error instanceof ApiClientError && error.turnId ? error.turnId : id;
      const retryable = !(error instanceof ApiClientError && error.code === "not_found");
      if (followTurnIdRef.current === id) {
        followTurnIdRef.current = persistedId;
      }
      if (pinTurnIdRef.current === id) {
        pinTurnIdRef.current = persistedId;
      }
      setTurns((current) =>
        current.map((turn) =>
          turn.id === id
            ? { ...turn, id: persistedId, error: message, retryable }
            : turn,
        ),
      );
      setActiveTurnId(persistedId);
    } finally {
      askingRef.current = false;
      setAsking(false);
    }
  }

  function noteLibraryChange() {
    if (turns.length > 0) {
      setLibraryChanged(true);
    }
  }

  async function handleDetails(documentId: string) {
    setDetailError(null);
    setDocumentActionError(null);
    try {
      setDetail(await getDocument(documentId));
    } catch {
      setDetail(null);
      setDetailError("Could not load document details.");
    }
  }

  async function handleReindex(documentId: string) {
    if (busyDocumentIdRef.current) {
      return;
    }
    busyDocumentIdRef.current = documentId;
    setBusyDocumentId(documentId);
    setBusyKind("reindex");
    setDocumentActionError(null);
    setDetailError(null);
    const startedAt = Date.now();
    await waitForPaint();
    try {
      const result = await reindexDocument(documentId);
      setDocuments((current) =>
        current.map((item) =>
          item.document_id === documentId ? result.document : item,
        ),
      );
      await refreshDocuments();
      noteLibraryChange();
    } catch (error) {
      const message =
        error instanceof ApiClientError
          ? describeApiFailure(error, "Re-index failed.")
          : "Re-index failed.";
      setDocumentActionError(message);
      await refreshDocuments();
    } finally {
      await keepBusyVisible(startedAt);
      busyDocumentIdRef.current = null;
      setBusyDocumentId(null);
      setBusyKind(null);
    }
  }

  async function handleDelete() {
    if (!pendingDelete || busyDocumentIdRef.current) {
      return;
    }
    busyDocumentIdRef.current = pendingDelete.document_id;
    setBusyDocumentId(pendingDelete.document_id);
    setBusyKind("delete");
    setDeleteError(null);
    try {
      await deleteDocument(pendingDelete.document_id);
      setPendingDelete(null);
      await refreshDocuments();
      noteLibraryChange();
    } catch (error) {
      const message =
        error instanceof ApiClientError ? error.message : "Could not remove the document.";
      setDeleteError(message);
    } finally {
      busyDocumentIdRef.current = null;
      setBusyDocumentId(null);
      setBusyKind(null);
    }
  }

  async function handleRename(title: string) {
    if (!pendingRename) {
      return;
    }
    setSessionBusy(true);
    setSessionError(null);
    try {
      await patchSession(pendingRename.session_id, { title });
      if (pendingRename.session_id === activeSessionIdRef.current) {
        setActiveTitle(title);
      }
      setPendingRename(null);
      await refreshSessionList();
    } catch (error) {
      setSessionError(error instanceof ApiClientError ? error.message : "Could not rename.");
    } finally {
      setSessionBusy(false);
    }
  }

  async function handleDeleteSession() {
    if (!pendingSessionDelete) {
      return;
    }
    setSessionBusy(true);
    setSessionError(null);
    const deletedId = pendingSessionDelete.session_id;
    try {
      await deleteSession(deletedId);
      setPendingSessionDelete(null);
      const listed = await refreshSessionList();
      if (!listed) {
        return;
      }
      if (activeSessionIdRef.current === deletedId) {
        const next = listed.find((item) => item.turn_count > 0);
        if (next) {
          await openSession(next.session_id);
        } else {
          startNewConversation();
        }
      }
    } catch (error) {
      setSessionError(error instanceof ApiClientError ? error.message : "Could not delete.");
    } finally {
      setSessionBusy(false);
    }
  }

  function focusCitation(turnId: string, citationId: string) {
    setActiveTurnId(turnId);
    setActiveCitationId(citationId);
    setPane("evidence");
  }

  const { dropActive, dropBind } = useFileDrop(
    ingestDroppedFiles,
    !uploading && !busyDocumentId,
  );

  return (
    <div
      className={dropActive ? "app is-drop-target" : "app"}
      data-testid="app-shell"
      {...dropBind}
    >
      <div
        className={dropActive ? "drop-overlay is-active" : "drop-overlay"}
        data-testid="drop-overlay"
        role="status"
        aria-live="polite"
        aria-hidden={!dropActive}
      >
        <p className="drop-overlay-message">Drop files to add them</p>
      </div>
      <header className="shell-header">
        <div className="shell-brand">
          <h1>Research Assistant</h1>
          <span className="shell-brand-separator" aria-hidden="true">·</span>
          <p className="active-research-title" title={activeTitle} data-testid="active-research-title">
            {sessionLoading ? "Loading research…" : activeTitle}
          </p>
        </div>
        <div className="shell-actions">
          <SessionSwitcher
            sessions={sessions}
            activeSessionId={activeSessionId}
            currentTitle={activeTitle}
            disabled={asking || sessionBusy}
            onOpen={(sessionId) => void openSession(sessionId)}
            onRename={setPendingRename}
            onDelete={setPendingSessionDelete}
          />
          <button
            type="button"
            className="btn btn-quiet"
            disabled={asking}
            onClick={startNewConversation}
          >
            New research
          </button>
        </div>
      </header>
      <StatusBanner ready={ready} healthError={healthError} />
      {sessionError && !pendingRename && !pendingSessionDelete ? (
        <div className="banner banner-warn" role="alert">
          {sessionError}
        </div>
      ) : null}
      {libraryChanged ? (
        <div className="banner banner-warn" role="status">
          The document set changed. Previous answers are unchanged; new questions use the current
          library.
        </div>
      ) : null}
      <WorkspaceLayout pane={pane} onPaneChange={setPane} documents={
        <DocumentSidebar
          documents={documents}
          selectedIds={selectedIds}
          allDocuments={scopeRef.current.mode === "all"}
          uploading={uploading}
          uploadFeedback={uploadFeedback}
          libraryLoadError={libraryError}
          documentActionError={
            pendingDelete
              ? null
              : documentActionError
          }
          busyDocumentId={busyDocumentId}
          busyKind={busyKind}
          filter={filter}
          onFilterChange={setFilter}
          onToggleDocument={toggleDocument}
          onSelectAll={selectAllDocuments}
          onClearSelection={clearDocumentSelection}
          onUpload={(files) => void handleUploadFiles(files)}
          onRetryFailedUploads={(files) => void handleUploadFiles(files)}
          onDismissUploadFeedback={() => setUploadFeedback(null)}
          onRetryLoad={() => void refreshDocuments()}
          onDetails={(documentId) => void handleDetails(documentId)}
          onReindex={(documentId) => void handleReindex(documentId)}
          onDelete={(document) => {
            setDeleteError(null);
            setPendingDelete(document);
          }}
        />
      } evidence={
        <SourcePanel
          sources={sources}
          activeCitationId={activeCitationId}
          knownDocumentIds={knownDocumentIds}
          onSelect={(citationId) => {
            setActiveCitationId(citationId);
            if (activeTurn) {
              setActiveTurnId(activeTurn.id);
            }
          }}
        />
      }>
        <main className="workspace" aria-label="Research conversation">
          <div
            className="pane-scroll"
            data-testid="conversation-scroll"
            ref={conversationScrollRef}
            onScroll={onConversationScroll}
          >
            {turns.length === 0 ? (
              <ConversationEmpty hasDocuments={documents.length > 0} />
            ) : (
              <ConversationErrorBoundary>
                <ol className="turns">
                {turns.map((turn) => (
                  <ConversationTurn
                    key={turn.id}
                    ref={bindTurnNode(turn.id)}
                    turnId={turn.id}
                    question={turn.question}
                    response={turn.response}
                    error={turn.error}
                    pending={asking && turn.id === activeTurnId}
                    retryable={turn.retryable !== false}
                    retryDisabled={!canAsk || sessionLoading || Boolean(scopeError)}
                    activeCitationId={turn.id === activeTurn?.id ? activeCitationId : null}
                    onCitationClick={(citationId) => focusCitation(turn.id, citationId)}
                    onRetry={() => void requestAnswer(turn.question, turn.id)}
                  />
                ))}
              </ol>
              </ConversationErrorBoundary>
            )}
            <div
              ref={followSpaceRef}
              className="conversation-follow-space"
              data-testid="conversation-follow-space"
              aria-hidden="true"
              style={{ height: pinSpace }}
            />
            <DiagnosticsPanel
              diagnostics={activeTurn?.response?.diagnostics ?? null}
              mode={mode}
              rerank={rerank}
              onModeChange={setMode}
              onRerankChange={setRerank}
            />
          </div>
          <div className="composer-dock">
            <div className="measure">
              <ResearchContext
                id={questionContextId}
                scope={scopeRef.current}
                libraryCount={documents.length}
                availableCount={selectedIds.length}
                saving={scopeSaving}
                error={scopeError}
                loading={sessionLoading}
                onRetry={retryScopeSave}
              />
              {asking ? (
                <p className="loading" role="status">
                  Working…
                </p>
              ) : documents.length > 0 && !canAsk ? (
                <p className="hint" role="status">
                  Select at least one document to ask a question.
                </p>
              ) : null}
              <QuestionInput
                value={question}
                disabled={asking}
                submitDisabled={!canAsk || sessionLoading || Boolean(scopeError)}
                describedById={questionContextId}
                textareaRef={composerRef}
                onChange={setComposerValue}
                onSubmit={(value) => {
                  const text = (
                    value ||
                    composerRef.current?.value ||
                    questionRef.current
                  ).trim();
                  void requestAnswer(text);
                }}
              />
            </div>
          </div>
        </main>
      </WorkspaceLayout>
      {detail ? <DocumentDetails detail={detail} onClose={() => setDetail(null)} /> : null}
      {detailError ? (
        <Dialog title="Document details" onClose={() => setDetailError(null)}
          dismissOnBackdrop testId="document-details-error">
          <p className="error" role="alert">
            {detailError}
          </p>
          <div className="dialog-actions">
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() => setDetailError(null)}
            >
              Close
            </button>
          </div>
        </Dialog>
      ) : null}
      {pendingDelete ? (
        <DeleteDocumentDialog
          filename={pendingDelete.filename}
          busy={busyDocumentId === pendingDelete.document_id}
          error={deleteError}
          onCancel={() => {
            if (!busyDocumentId) {
              setPendingDelete(null);
              setDeleteError(null);
            }
          }}
          onConfirm={() => void handleDelete()}
        />
      ) : null}
      {pendingRename ? (
        <RenameSessionDialog
          title={pendingRename.title}
          busy={sessionBusy}
          error={sessionError}
          onCancel={() => {
            if (!sessionBusy) {
              setPendingRename(null);
              setSessionError(null);
            }
          }}
          onConfirm={(title) => void handleRename(title)}
        />
      ) : null}
      {pendingSessionDelete ? (
        <DeleteSessionDialog
          title={pendingSessionDelete.title}
          busy={sessionBusy}
          error={sessionError}
          onCancel={() => {
            if (!sessionBusy) {
              setPendingSessionDelete(null);
              setSessionError(null);
            }
          }}
          onConfirm={() => void handleDeleteSession()}
        />
      ) : null}
    </div>
  );
}
