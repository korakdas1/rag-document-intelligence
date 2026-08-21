import { createEvent, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { ApiClientError } from "./api/client";
import type { AskResponse, DocumentSummary, SessionSummary, SessionTurnView } from "./api/types";
import { TURN_TOP_PAD, turnIsVisibleInPane } from "./conversationScroll";
import { UNSUPPORTED_UPLOAD_MESSAGE } from "./uploadAccept";

vi.mock("./api/health", () => ({
  getHealth: vi.fn(),
  getReady: vi.fn(),
}));
vi.mock("./api/documents", () => ({
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
  getDocument: vi.fn(),
  reindexDocument: vi.fn(),
  deleteDocument: vi.fn(),
}));
vi.mock("./api/ask", () => ({
  askQuestion: vi.fn(),
}));
vi.mock("./api/sessions", () => ({
  listSessions: vi.fn(),
  getSession: vi.fn(),
  createSession: vi.fn(),
  patchSession: vi.fn(),
  deleteSession: vi.fn(),
}));

import { askQuestion } from "./api/ask";
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

const mockedHealth = vi.mocked(getHealth);
const mockedReady = vi.mocked(getReady);
const mockedList = vi.mocked(listDocuments);
const mockedUpload = vi.mocked(uploadDocument);
const mockedAsk = vi.mocked(askQuestion);
const mockedGet = vi.mocked(getDocument);
const mockedReindex = vi.mocked(reindexDocument);
const mockedDelete = vi.mocked(deleteDocument);
const mockedListSessions = vi.mocked(listSessions);
const mockedGetSession = vi.mocked(getSession);
const mockedCreateSession = vi.mocked(createSession);
const mockedPatchSession = vi.mocked(patchSession);
const mockedDeleteSession = vi.mocked(deleteSession);

function sessionRow(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    session_id: "sess-1",
    title: "New research",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    turn_count: 0,
    all_documents: true,
    ...overrides,
  };
}

function documentRow(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    document_id: "doc-1",
    filename: "attention.md",
    content_type: "text/markdown",
    status: "ready",
    page_count: 1,
    chunk_count: 1,
    byte_size: 12,
    warning_count: 0,
    ingested_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    parse_status: "parsed",
    error_message: null,
    ...overrides,
  };
}

function askResponse(overrides: Partial<AskResponse> = {}): AskResponse {
  return {
    question: "What is attention?",
    answer: "Transformers use self-attention [S1].",
    grounding_status: "grounded",
    validation_status: "valid",
    insufficient_evidence: false,
    citations: [
      {
        citation_id: "S1",
        filename: "attention.md",
        document_id: "doc-1",
        page_start: 1,
        page_end: 1,
        section_path: ["Architecture"],
        locator: 'attention.md, p. 1, section "Architecture"',
        occurrence_count: 1,
      },
    ],
    sources: [
      {
        citation_id: "S1",
        filename: "attention.md",
        document_id: "doc-1",
        page_start: 1,
        page_end: 1,
        section_path: ["Architecture"],
        locator: 'attention.md, p. 1, section "Architecture"',
        text: "Self-attention allows each token to attend to every other token.",
        truncated: false,
        cited_by_model: true,
      },
    ],
    diagnostics: {
      retrieval_mode: "hybrid",
      rerank_enabled: true,
      candidate_count: 1,
      context_source_count: 1,
      dense_ms: 1,
      lexical_ms: 1,
      fusion_ms: 0,
      retrieval_ms: 2,
      rerank_ms: 0,
      generation_ms: 8,
      llm_id: "scripted",
      reranker_id: "overlap",
      validation_status: "valid",
      candidates: [],
    },
    request_id: "a1",
    ...overrides,
  };
}

describe("App", () => {
  beforeEach(() => {
    mockedAsk.mockReset();
    mockedUpload.mockReset();
    mockedGet.mockReset();
    mockedReindex.mockReset();
    mockedDelete.mockReset();
    mockedListSessions.mockReset();
    mockedGetSession.mockReset();
    mockedCreateSession.mockReset();
    mockedPatchSession.mockReset();
    mockedDeleteSession.mockReset();
    mockedHealth.mockResolvedValue({
      status: "ok",
      service: "research-assistant",
      request_id: "h1",
    });
    mockedReady.mockResolvedValue({
      status: "ready",
      database: { status: "ok", detail: "" },
      vector_store: { status: "ok", detail: "" },
      llm_provider: { status: "ok", detail: "scripted" },
      embedding: { status: "configured", detail: "hashing" },
      request_id: "r1",
    });
    mockedList.mockResolvedValue({
      documents: [],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedListSessions.mockResolvedValue({ sessions: [], request_id: "s1" });
    mockedCreateSession.mockResolvedValue(sessionRow());
    mockedPatchSession.mockResolvedValue(sessionRow());
    mockedAsk.mockResolvedValue(askResponse({ session_id: "sess-1", turn_id: "turn-1" }));
  });

  it("shows the empty library state", async () => {
    render(<App />);
    expect(
      await screen.findByText(
        "Add a PDF, Markdown, or text document to start asking questions.",
      ),
    ).toBeInTheDocument();
  });

  it("empty research has no Try-a-question controls", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    render(<App />);
    expect(await screen.findByText("Ask a question about your documents.")).toBeInTheDocument();
    expect(screen.queryByText("Try a question")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Summarize the selected documents/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /What are the key facts in these documents/i }),
    ).not.toBeInTheDocument();
  });

  describe("composer submit", () => {
    async function renderWithDocs() {
      mockedList.mockResolvedValue({
        documents: [documentRow()],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      const user = userEvent.setup();
      const view = render(<App />);
      await screen.findByText("attention.md");
      return { user, ...view };
    }

    it("B: Enter submits the typed question once", async () => {
      const { user } = await renderWithDocs();
      await user.type(
        screen.getByLabelText("Research question"),
        "What are the key facts in these documents?",
      );
      await user.keyboard("{Enter}");
      await waitFor(() => {
        expect(mockedAsk).toHaveBeenCalledTimes(1);
      });
      expect(mockedAsk.mock.calls[0][0].question).toBe("What are the key facts in these documents?");
      expect(screen.getByTestId("app-shell")).toBeInTheDocument();
      expect(screen.getByLabelText("Research question").closest("form")).toBeNull();
    });

    it("C: Ask question submits the typed text once", async () => {
      const { user } = await renderWithDocs();
      await user.type(screen.getByLabelText("Research question"), "Where did the depot open?");
      await user.click(screen.getByRole("button", { name: "Ask question" }));
      await waitFor(() => {
        expect(mockedAsk).toHaveBeenCalledTimes(1);
      });
      expect(mockedAsk.mock.calls[0][0].question).toBe("Where did the depot open?");
    });

    it("D: Shift+Enter does not submit", async () => {
      const { user } = await renderWithDocs();
      await user.type(screen.getByLabelText("Research question"), "line one");
      await user.keyboard("{Shift>}{Enter}{/Shift}");
      expect(mockedAsk).not.toHaveBeenCalled();
    });

    it("E: successful submit keeps the SPA rendered", async () => {
      const { user } = await renderWithDocs();
      await user.type(screen.getByLabelText("Research question"), "What is attention?");
      await user.keyboard("{Enter}");
      expect(await screen.findByText("Grounded")).toBeInTheDocument();
      expect(screen.getByTestId("app-shell")).toBeInTheDocument();
      expect(screen.getByLabelText("Research question")).toBeInTheDocument();
    });

    it("repeated Enter does not duplicate the turn", async () => {
      let finish: ((value: AskResponse) => void) | undefined;
      mockedAsk.mockImplementation(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      );
      const { user } = await renderWithDocs();
      await user.type(screen.getByLabelText("Research question"), "What is attention?");
      await user.keyboard("{Enter}{Enter}{Enter}");
      expect(mockedAsk).toHaveBeenCalledTimes(1);
      finish?.(askResponse({ question: "What is attention?", turn_id: "turn-1" }));
      expect(await screen.findByText("Grounded")).toBeInTheDocument();
      expect(mockedAsk).toHaveBeenCalledTimes(1);
    });

    it("F: refresh restores the typed question and answer", async () => {
      const { user, unmount } = await renderWithDocs();
      mockedAsk.mockResolvedValue(
        askResponse({ question: "What is attention?", session_id: "sess-1", turn_id: "turn-1" }),
      );
      await user.type(screen.getByLabelText("Research question"), "What is attention?");
      await user.keyboard("{Enter}");
      expect(await screen.findByText("Grounded")).toBeInTheDocument();
      mockedListSessions.mockResolvedValue({
        sessions: [sessionRow({ turn_count: 1 })],
        request_id: "s2",
      });
      mockedGetSession.mockResolvedValue({
        ...sessionRow({ turn_count: 1 }),
        selected_document_ids: ["doc-1"],
        missing_selected_count: 0,
        turns: [
          {
            turn_id: "turn-1",
            sequence: 1,
            question: "What is attention?",
            answer: "Transformers use self-attention [S1].",
            grounding_status: "grounded",
            citations: [],
            sources: [],
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      });
      unmount();
      render(<App />);
      expect(await screen.findByText("What is attention?")).toBeInTheDocument();
      expect(screen.getByText(/Transformers use self-attention/)).toBeInTheDocument();
    });

    it("New research then typed question goes to a new session", async () => {
      mockedCreateSession
        .mockResolvedValueOnce(sessionRow({ session_id: "sess-1" }))
        .mockResolvedValueOnce(sessionRow({ session_id: "sess-new" }));
      mockedAsk
        .mockResolvedValueOnce(
          askResponse({
            question: "First question",
            session_id: "sess-1",
            turn_id: "turn-1",
          }),
        )
        .mockResolvedValueOnce(
          askResponse({
            question: "Second question",
            session_id: "sess-new",
            turn_id: "turn-new",
          }),
        );
      const { user } = await renderWithDocs();
      await user.type(screen.getByLabelText("Research question"), "First question");
      await user.keyboard("{Enter}");
      expect(await screen.findByText("Grounded")).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "New research" }));
      await user.type(screen.getByLabelText("Research question"), "Second question");
      await user.keyboard("{Enter}");
      await waitFor(() => {
        expect(mockedAsk).toHaveBeenCalledTimes(2);
      });
      expect(mockedAsk.mock.calls[1][0].session_id).toBe("sess-new");
      expect(mockedAsk.mock.calls[1][0].question).toBe("Second question");
    });
  });

  describe("first-turn New research pin", () => {
    const VIEWPORT = 480;
    let restoreGeometry: (() => void) | undefined;

    function layoutRect(top: number, height: number): DOMRect {
      return {
        x: 0,
        y: top,
        width: 400,
        height,
        top,
        left: 0,
        bottom: top + height,
        right: 400,
        toJSON() {
          return {};
        },
      };
    }

    function installShortPaneGeometry() {
      const elementProto = Element.prototype;
      const clientDesc =
        Object.getOwnPropertyDescriptor(Element.prototype, "clientHeight") ??
        Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientHeight");
      const scrollDesc =
        Object.getOwnPropertyDescriptor(Element.prototype, "scrollHeight") ??
        Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollHeight");
      vi.spyOn(elementProto, "getBoundingClientRect").mockImplementation(function (
        this: HTMLElement,
      ) {
        if (this.getAttribute("data-testid") === "conversation-scroll") {
          return layoutRect(0, VIEWPORT);
        }
        if (this.classList.contains("turn")) {
          const pane = this.closest("[data-testid='conversation-scroll']");
          return layoutRect(24 - (pane?.scrollTop ?? 0), 80);
        }
        return layoutRect(0, 0);
      });
      Object.defineProperty(Element.prototype, "clientHeight", {
        configurable: true,
        get(this: Element) {
          if (this.getAttribute("data-testid") === "conversation-scroll") {
            return VIEWPORT;
          }
          return clientDesc?.get?.call(this) ?? 0;
        },
      });
      Object.defineProperty(Element.prototype, "scrollHeight", {
        configurable: true,
        get(this: Element) {
          if (this.getAttribute("data-testid") === "conversation-scroll") {
            const n = this.querySelectorAll("li.turn").length;
            // Intentionally ignore spacer height so an unbounded pin loop is detectable.
            return 24 + n * 80 + 48;
          }
          return scrollDesc?.get?.call(this) ?? 0;
        },
      });
      return () => {
        vi.mocked(elementProto.getBoundingClientRect).mockRestore();
        if (clientDesc) {
          Object.defineProperty(Element.prototype, "clientHeight", clientDesc);
        }
        if (scrollDesc) {
          Object.defineProperty(Element.prototype, "scrollHeight", scrollDesc);
        }
      };
    }

    beforeEach(() => {
      restoreGeometry = installShortPaneGeometry();
    });

    afterEach(() => {
      restoreGeometry?.();
      restoreGeometry = undefined;
    });

    it("A: ALL scope first question settles without a render loop", async () => {
      mockedList.mockResolvedValue({
        documents: [documentRow()],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      const user = userEvent.setup();
      render(<App />);
      await screen.findByText("attention.md");
      await user.type(
        screen.getByLabelText("Research question"),
        "What are the key facts in these documents?",
      );
      await user.keyboard("{Enter}");
      expect(await screen.findByText("Grounded")).toBeInTheDocument();
      expect(screen.getByTestId("app-shell")).toBeInTheDocument();
      expect(screen.getByText("What are the key facts in these documents?")).toBeInTheDocument();
      expect(mockedAsk).toHaveBeenCalledTimes(1);
      expect(mockedCreateSession).toHaveBeenCalledTimes(1);
      expect(mockedPatchSession.mock.calls.length).toBeLessThan(3);
      expect(
        Number.parseFloat(screen.getByTestId("conversation-follow-space").style.height) || 0,
      ).toBeLessThanOrEqual(VIEWPORT);
    });

    it("B: SUBSET scope first question settles without a render loop", async () => {
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-2", filename: "other.md" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      const user = userEvent.setup();
      render(<App />);
      await screen.findByText("other.md");
      await user.click(screen.getByRole("checkbox", { name: /other.md/ }));
      await user.type(screen.getByLabelText("Research question"), "Subset first question");
      await user.click(screen.getByRole("button", { name: "Ask question" }));
      expect(await screen.findByText("Grounded")).toBeInTheDocument();
      expect(screen.getByTestId("app-shell")).toBeInTheDocument();
      expect(mockedAsk).toHaveBeenCalledTimes(1);
      expect(mockedAsk.mock.calls[0][0].question).toBe("Subset first question");
      expect(mockedCreateSession).toHaveBeenCalledTimes(1);
    });

    it("C: NONE scope does not submit a first question", async () => {
      mockedList.mockResolvedValue({
        documents: [documentRow()],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      const user = userEvent.setup();
      render(<App />);
      await screen.findByText("attention.md");
      await user.click(screen.getByRole("checkbox", { name: "Ask across all documents" }));
      expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();
      await user.type(screen.getByLabelText("Research question"), "Should not send");
      await user.keyboard("{Enter}");
      expect(mockedAsk).not.toHaveBeenCalled();
      expect(mockedCreateSession).not.toHaveBeenCalled();
      expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    });

    it("existing session next question still settles", async () => {
      mockedList.mockResolvedValue({
        documents: [documentRow()],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [sessionRow({ turn_count: 1 })],
        request_id: "s1",
      });
      mockedGetSession.mockResolvedValue({
        ...sessionRow({ turn_count: 1 }),
        selected_document_ids: ["doc-1"],
        missing_selected_count: 0,
        turns: [
          {
            turn_id: "t1",
            sequence: 1,
            question: "Prior question",
            answer: "Prior answer [S1].",
            grounding_status: "grounded",
            citations: [],
            sources: [],
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      });
      const user = userEvent.setup();
      render(<App />);
      expect(await screen.findByText("Prior question")).toBeInTheDocument();
      await user.type(screen.getByLabelText("Research question"), "Follow-up question");
      await user.keyboard("{Enter}");
      expect(await screen.findByText("Follow-up question")).toBeInTheDocument();
      expect(screen.getAllByText("Grounded").length).toBeGreaterThan(0);
      expect(mockedAsk).toHaveBeenCalledTimes(1);
      expect(mockedCreateSession).not.toHaveBeenCalled();
      expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    });
  });

  describe("document scope", () => {
    it("A: restores ALL mode after reload", async () => {
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-2", filename: "other.md" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [sessionRow({ turn_count: 1, all_documents: true })],
        request_id: "s1",
      });
      mockedGetSession.mockResolvedValue({
        ...sessionRow({ turn_count: 1, all_documents: true }),
        selected_document_ids: [],
        missing_selected_count: 0,
        turns: [
          {
            turn_id: "t1",
            sequence: 1,
            question: "Where?",
            answer: "Vermont [S1].",
            grounding_status: "grounded",
            citations: [],
            sources: [],
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      });
      render(<App />);
      expect(await screen.findByText("Where?")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: "Ask across all documents" })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: /other.md/ })).toBeChecked();
    });

    it("B: restores a subset after reload", async () => {
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-2", filename: "other.md" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [sessionRow({ turn_count: 1, all_documents: false })],
        request_id: "s1",
      });
      mockedGetSession.mockResolvedValue({
        ...sessionRow({ turn_count: 1, all_documents: false }),
        selected_document_ids: ["doc-2"],
        missing_selected_count: 0,
        turns: [
          {
            turn_id: "t1",
            sequence: 1,
            question: "Limits?",
            answer: "Insufficient evidence.",
            grounding_status: "insufficient_evidence",
            citations: [],
            sources: [],
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      });
      render(<App />);
      expect(await screen.findByText("Limits?")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).not.toBeChecked();
      expect(screen.getByRole("checkbox", { name: /other.md/ })).toBeChecked();
    });

    it("C: restores none selected", async () => {
      mockedList.mockResolvedValue({
        documents: [documentRow()],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [sessionRow({ turn_count: 1, all_documents: false })],
        request_id: "s1",
      });
      mockedGetSession.mockResolvedValue({
        ...sessionRow({ turn_count: 1, all_documents: false }),
        selected_document_ids: [],
        missing_selected_count: 0,
        turns: [
          {
            turn_id: "t1",
            sequence: 1,
            question: "Q",
            answer: "A",
            grounding_status: "grounded",
            citations: [],
            sources: [],
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      });
      render(<App />);
      expect(await screen.findByText("Q")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).not.toBeChecked();
      expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();
    });

    it("D: switching sessions restores each scope", async () => {
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-2", filename: "other.md" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [
          sessionRow({ session_id: "sess-a", title: "All scope", turn_count: 1, all_documents: true }),
          sessionRow({ session_id: "sess-b", title: "Subset", turn_count: 1, all_documents: false }),
        ],
        request_id: "s1",
      });
      mockedGetSession.mockImplementation(async (id: string) => {
        if (id === "sess-b") {
          return {
            ...sessionRow({ session_id: "sess-b", title: "Subset", turn_count: 1, all_documents: false }),
            selected_document_ids: ["doc-2"],
            missing_selected_count: 0,
            turns: [
              {
                turn_id: "tb",
                sequence: 1,
                question: "Subset Q",
                answer: "Subset A",
                grounding_status: "grounded",
                citations: [],
                sources: [],
                created_at: "2026-01-01T00:00:00Z",
              },
            ],
          };
        }
        return {
          ...sessionRow({ session_id: "sess-a", title: "All scope", turn_count: 1, all_documents: true }),
          selected_document_ids: [],
          missing_selected_count: 0,
          turns: [
            {
              turn_id: "ta",
              sequence: 1,
              question: "All Q",
              answer: "All A",
              grounding_status: "grounded",
              citations: [],
              sources: [],
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        };
      });
      const user = userEvent.setup();
      render(<App />);
      expect(await screen.findByText("All Q")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /other.md/ })).toBeChecked();
      await user.click(screen.getByRole("button", { name: "History" }));
      await user.click(screen.getByRole("menuitem", { name: /Subset/ }));
      expect(await screen.findByText("Subset Q")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).not.toBeChecked();
      expect(screen.getByRole("checkbox", { name: /other.md/ })).toBeChecked();
    });

    it("E: drops a deleted document from a subset", async () => {
      mockedList.mockResolvedValue({
        documents: [documentRow()],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [sessionRow({ turn_count: 1, all_documents: false })],
        request_id: "s1",
      });
      mockedGetSession.mockResolvedValue({
        ...sessionRow({ turn_count: 1, all_documents: false }),
        selected_document_ids: ["doc-1", "missing-doc"],
        missing_selected_count: 1,
        turns: [
          {
            turn_id: "t1",
            sequence: 1,
            question: "Q",
            answer: "A",
            grounding_status: "grounded",
            citations: [],
            sources: [],
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      });
      render(<App />);
      expect(await screen.findByText("Q")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).toBeChecked();
      expect(screen.queryByText("missing-doc")).not.toBeInTheDocument();
    });

    it("F: ALL mode includes a newly uploaded document", async () => {
      mockedList.mockResolvedValue({
        documents: [documentRow()],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedUpload.mockResolvedValue({
        document: documentRow({ document_id: "doc-new", filename: "fresh.md" }),
        outcome: "created",
        warnings: [],
        request_id: "u1",
      });
      const user = userEvent.setup();
      render(<App />);
      await screen.findByText("attention.md");
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).toBeChecked();
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-new", filename: "fresh.md" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d2",
      });
      await user.upload(
        document.querySelector('input[type="file"]') as HTMLInputElement,
        new File(["#"], "fresh.md", { type: "text/markdown" }),
      );
      expect(await screen.findByText("fresh.md")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /fresh.md/ })).toBeChecked();
    });

    it("J: switching back to NONE restores none", async () => {
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-2", filename: "other.md" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [
          sessionRow({ session_id: "sess-none", title: "None scope", turn_count: 1, all_documents: false }),
          sessionRow({ session_id: "sess-all", title: "All scope", turn_count: 1, all_documents: true }),
        ],
        request_id: "s1",
      });
      mockedGetSession.mockImplementation(async (id: string) => {
        if (id === "sess-all") {
          return {
            ...sessionRow({ session_id: "sess-all", title: "All scope", turn_count: 1, all_documents: true }),
            selected_document_ids: [],
            missing_selected_count: 0,
            turns: [
              {
                turn_id: "ta",
                sequence: 1,
                question: "All Q",
                answer: "All A",
                grounding_status: "grounded",
                citations: [],
                sources: [],
                created_at: "2026-01-01T00:00:00Z",
              },
            ],
          };
        }
        return {
          ...sessionRow({ session_id: "sess-none", title: "None scope", turn_count: 1, all_documents: false }),
          selected_document_ids: [],
          missing_selected_count: 0,
          turns: [
            {
              turn_id: "tn",
              sequence: 1,
              question: "None Q",
              answer: "None A",
              grounding_status: "grounded",
              citations: [],
              sources: [],
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        };
      });
      const user = userEvent.setup();
      render(<App />);
      expect(await screen.findByText("None Q")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).not.toBeChecked();
      await user.click(screen.getByRole("button", { name: "History" }));
      await user.click(screen.getByRole("menuitem", { name: /All scope/ }));
      expect(await screen.findByText("All Q")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).toBeChecked();
      await user.click(screen.getByRole("button", { name: "History" }));
      await user.click(screen.getByRole("menuitem", { name: /None scope/ }));
      expect(await screen.findByText("None Q")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).not.toBeChecked();
      expect(screen.getByRole("checkbox", { name: /other.md/ })).not.toBeChecked();
      expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();
    });

    it("K: NONE mode does not auto-select a later upload", async () => {
      mockedList.mockResolvedValue({
        documents: [documentRow()],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [sessionRow({ turn_count: 1, all_documents: false })],
        request_id: "s1",
      });
      mockedGetSession.mockResolvedValue({
        ...sessionRow({ turn_count: 1, all_documents: false }),
        selected_document_ids: [],
        missing_selected_count: 0,
        turns: [
          {
            turn_id: "t1",
            sequence: 1,
            question: "Q",
            answer: "A",
            grounding_status: "grounded",
            citations: [],
            sources: [],
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      });
      mockedUpload.mockResolvedValue({
        document: documentRow({ document_id: "doc-new", filename: "fresh.md" }),
        outcome: "created",
        warnings: [],
        request_id: "u1",
      });
      const user = userEvent.setup();
      render(<App />);
      expect(await screen.findByText("Q")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).not.toBeChecked();
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-new", filename: "fresh.md" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d2",
      });
      await user.upload(
        document.querySelector('input[type="file"]') as HTMLInputElement,
        new File(["#"], "fresh.md", { type: "text/markdown" }),
      );
      expect(await screen.findByText("fresh.md")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).not.toBeChecked();
      expect(screen.getByRole("checkbox", { name: /fresh.md/ })).not.toBeChecked();
    });

    it("L: New research defaults to ALL", async () => {
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-2", filename: "other.md" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [sessionRow({ turn_count: 1, all_documents: false })],
        request_id: "s1",
      });
      mockedGetSession.mockResolvedValue({
        ...sessionRow({ turn_count: 1, all_documents: false }),
        selected_document_ids: ["doc-2"],
        missing_selected_count: 0,
        turns: [
          {
            turn_id: "t1",
            sequence: 1,
            question: "Subset Q",
            answer: "Subset A",
            grounding_status: "grounded",
            citations: [],
            sources: [],
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      });
      const user = userEvent.setup();
      render(<App />);
      expect(await screen.findByText("Subset Q")).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "New research" }));
      expect(screen.getByRole("checkbox", { name: "Ask across all documents" })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: /other.md/ })).toBeChecked();
    });

    it("persists explicit NONE instead of coercing it to ALL", async () => {
      mockedList.mockResolvedValue({
        documents: [documentRow()],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [sessionRow({ turn_count: 1, all_documents: true })],
        request_id: "s1",
      });
      mockedGetSession.mockResolvedValue({
        ...sessionRow({ turn_count: 1, all_documents: true }),
        selected_document_ids: [],
        missing_selected_count: 0,
        turns: [
          {
            turn_id: "t1",
            sequence: 1,
            question: "Q",
            answer: "A",
            grounding_status: "grounded",
            citations: [],
            sources: [],
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      });
      const user = userEvent.setup();
      render(<App />);
      expect(await screen.findByText("Q")).toBeInTheDocument();
      await user.click(screen.getByRole("checkbox", { name: "Ask across all documents" }));
      await waitFor(() => {
        expect(mockedPatchSession).toHaveBeenCalled();
      });
      const last = mockedPatchSession.mock.calls.at(-1)?.[1];
      expect(last).toMatchObject({ all_documents: false, selected_document_ids: [] });
    });
  });

  it("New research does not open History", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.click(screen.getByRole("button", { name: "New research" }));
    expect(screen.queryByRole("menu", { name: "Research history" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask question" })).toBeInTheDocument();
  });

  it("surfaces upload errors without crashing", async () => {
    mockedUpload.mockRejectedValue(
      new ApiClientError("unsupported_type", "Unsupported file type.", 400),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Documents" }));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["not a supported payload"], "notes.md", {
      type: "text/markdown",
    });
    await user.upload(input, file);
    expect(await screen.findByText("Unsupported file type.")).toBeInTheDocument();
  });

  it("does not show raw CUDA dumps for a resource-exhausted upload", async () => {
    mockedUpload.mockRejectedValue(
      new ApiClientError(
        "resource_exhausted",
        "CUDA out of memory. Tried to allocate 2.00 GiB. PyTorch allocator.",
        503,
      ),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "Documents" }));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(["x"], "paper.pdf", { type: "application/pdf" }));
    const error = await screen.findByTestId("upload-error");
    expect(error).toHaveTextContent("Could not index paper.pdf");
    expect(error).not.toHaveTextContent("CUDA");
    expect(error).not.toHaveTextContent("PyTorch");
  });

  it("opens the matching source when a citation is clicked", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedAsk.mockResolvedValue(askResponse());
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Grounded")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "[S1]" }));
    await waitFor(() => {
      expect(
        screen.getByText("Self-attention allows each token to attend to every other token."),
      ).toBeVisible();
    });
    expect(document.getElementById("source-S1")).toHaveAttribute("aria-current", "true");
  });

  it("sends selected document ids when the corpus is narrowed", async () => {
    mockedList.mockResolvedValue({
      documents: [
        documentRow(),
        documentRow({ document_id: "doc-2", filename: "other.md" }),
      ],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedAsk.mockResolvedValue(askResponse({ sources: [], citations: [] }));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("other.md");
    await user.click(screen.getByText("other.md"));
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    await waitFor(() => {
      expect(mockedAsk).toHaveBeenCalled();
    });
    expect(mockedAsk.mock.calls[0][0].document_ids).toEqual(["doc-1"]);
  });

  it("sends bounded conversation on follow-up and can clear it", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedAsk.mockResolvedValue(
      askResponse({
        citations: [],
        sources: [],
        diagnostics: {
          retrieval_mode: "hybrid",
          rerank_enabled: true,
          candidate_count: 1,
          context_source_count: 1,
          dense_ms: 1,
          lexical_ms: 1,
          fusion_ms: 0,
          retrieval_ms: 2,
          rerank_ms: 0,
          generation_ms: 8,
          llm_id: "scripted",
          reranker_id: "overlap",
          validation_status: "valid",
          candidates: [],
          rewrite_applied: false,
        },
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Grounded")).toBeInTheDocument();
    expect(mockedAsk.mock.calls[0][0].conversation).toEqual([]);

    mockedAsk.mockResolvedValueOnce(
      askResponse({
        question: "Why?",
        answer: "Because the notes describe self-attention [S1].",
        citations: [],
        sources: [],
        diagnostics: {
          retrieval_mode: "hybrid",
          rerank_enabled: true,
          candidate_count: 1,
          context_source_count: 1,
          dense_ms: 1,
          lexical_ms: 1,
          fusion_ms: 0,
          retrieval_ms: 2,
          rerank_ms: 0,
          generation_ms: 8,
          llm_id: "scripted",
          reranker_id: "overlap",
          validation_status: "valid",
          candidates: [],
          rewrite_applied: true,
          original_question: "Why?",
          retrieval_query: "Why, regarding attention?",
        },
        request_id: "a2",
      }),
    );
    await user.type(screen.getByLabelText("Research question"), "Why?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    await waitFor(() => {
      expect(mockedAsk.mock.calls.length).toBe(2);
    });
    expect(mockedAsk.mock.calls[1][0].conversation).toEqual([
      {
        question: "What is attention?",
        answer: "Transformers use self-attention [S1].",
        grounding_status: "grounded",
      },
    ]);
    expect(screen.getByText("What is attention?")).toBeInTheDocument();
    expect(screen.getByText("Why?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "New research" }));
    expect(screen.queryByText("What is attention?")).not.toBeInTheDocument();
  });

  it("keeps developer details collapsed until requested", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedAsk.mockResolvedValue(askResponse());
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    expect(screen.queryByLabelText("Retrieval mode")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Developer details" }));
    expect(screen.getByLabelText("Retrieval mode")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Grounded")).toBeInTheDocument();
    expect(screen.getByText("hybrid")).toBeInTheDocument();
  });

  it("retries a failed question without inventing an answer", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    const persistedTurnId = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    mockedAsk.mockRejectedValueOnce(
      new ApiClientError(
        "provider_unavailable",
        "LLM provider unavailable: [Errno 111] Connection refused",
        503,
        "r1",
        { turnId: persistedTurnId, sessionId: "sess-1" },
      ),
    );
    mockedAsk.mockResolvedValueOnce(
      askResponse({ session_id: "sess-1", turn_id: persistedTurnId }),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(
      await screen.findByText("LLM provider unavailable: [Errno 111] Connection refused"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Insufficient evidence")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Grounded")).toBeInTheDocument();
    expect(mockedAsk).toHaveBeenCalledTimes(2);
    expect(mockedAsk.mock.calls[0][0].replace_turn_id).toBeUndefined();
    expect(mockedAsk.mock.calls[1][0].replace_turn_id).toBe(persistedTurnId);
    expect(mockedAsk.mock.calls[1][0].question).toBe("What is attention?");
    expect(mockedAsk.mock.calls[1][0].session_id).toBe("sess-1");
    expect(mockedAsk.mock.calls[0][0].session_id).toBe("sess-1");
  });

  it("opens document details from the library actions menu", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedGet.mockResolvedValue({
      ...documentRow(),
      chunker_id: "structure.v1:test",
      parser_id: "markdown.v1",
      warnings: ["low contrast figure"],
      checksum_sha256: "abc123def456",
      index_status: "ready",
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.click(screen.getByRole("button", { name: "Actions for attention.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Details" }));
    expect(await screen.findByText("markdown.v1")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "attention.md" })).toBeInTheDocument();
  });

  it("confirms deletion, refreshes the library, and drops the selected id", async () => {
    mockedList.mockResolvedValue({
      documents: [
        documentRow(),
        documentRow({ document_id: "doc-2", filename: "other.md" }),
      ],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedDelete.mockResolvedValue({
      document_id: "doc-2",
      deleted: true,
      already_absent: false,
      vector_cleanup_status: "purged",
      request_id: "x",
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("other.md");
    await user.click(screen.getByText("attention.md"));
    await user.click(screen.getByRole("button", { name: "Actions for other.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Remove" }));
    expect(
      screen.getByText(/Indexed chunks and vectors will be removed/),
    ).toBeInTheDocument();
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d2",
    });
    await user.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => {
      expect(mockedDelete).toHaveBeenCalledWith("doc-2");
    });
    await waitFor(() => {
      expect(screen.queryByText("other.md")).not.toBeInTheDocument();
    });
  });

  it("surfaces a failed delete without removing the document", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedDelete.mockRejectedValue(
      new ApiClientError("vector_cleanup_failed", "Could not remove indexed vectors.", 503),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.click(screen.getByRole("button", { name: "Actions for attention.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Remove" }));
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(await screen.findByText("Could not remove indexed vectors.")).toBeInTheDocument();
    expect(screen.getByTitle("attention.md")).toBeInTheDocument();
  });

  it("re-indexes from the actions menu", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedReindex.mockResolvedValue({
      document: documentRow(),
      outcome: "unchanged",
      warnings: [],
      request_id: "r1",
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.click(screen.getByRole("button", { name: "Actions for attention.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Re-index" }));
    await waitFor(() => {
      expect(mockedReindex).toHaveBeenCalledWith("doc-1");
    });
    await waitFor(() => {
      expect(screen.queryByText("Re-indexing…")).not.toBeInTheDocument();
    });
  });

  it("restores a saved session after load", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedListSessions.mockResolvedValue({
      sessions: [sessionRow({ title: "Prior work", turn_count: 1 })],
      request_id: "s1",
    });
    mockedGetSession.mockResolvedValue({
      ...sessionRow({ title: "Prior work", turn_count: 1 }),
      selected_document_ids: ["doc-1"],
      missing_selected_count: 0,
      turns: [
        {
          turn_id: "t1",
          sequence: 1,
          question: "What is attention?",
          answer: "Transformers use self-attention [S1].",
          grounding_status: "grounded",
          citations: [],
          sources: [],
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    render(<App />);
    expect(await screen.findByText("What is attention?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "History" })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "History" }));
    expect(screen.getByRole("menuitem", { name: /Prior work/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
  });

  it("does not restore a stale provider error over a successful retried turn", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedListSessions.mockResolvedValue({
      sessions: [sessionRow({ title: "Harry notes", turn_count: 1 })],
      request_id: "s1",
    });
    mockedGetSession.mockResolvedValue({
      ...sessionRow({ title: "Harry notes", turn_count: 1 }),
      selected_document_ids: [],
      missing_selected_count: 0,
      turns: [
        {
          turn_id: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          sequence: 1,
          question: "Where were Harry and Hermione married?",
          answer: "The documents do not describe that wedding [S1].",
          grounding_status: "unverified",
          error_message: "LLM provider unavailable: [Errno 111] Connection refused",
          citations: [],
          sources: [
            {
              citation_id: "S1",
              filename: "attention.md",
              document_id: "doc-1",
              page_start: 1,
              page_end: 1,
              section_path: [],
              locator: "attention.md, p. 1",
              text: "Connection refused is a socket error.",
              truncated: false,
              cited_by_model: false,
            },
          ],
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    render(<App />);
    expect(
      await screen.findByText("Where were Harry and Hermione married?"),
    ).toBeInTheDocument();
    expect(screen.getByText("Unverified")).toBeInTheDocument();
    expect(screen.getByText(/do not describe that wedding/)).toBeInTheDocument();
    expect(
      screen.queryByText("LLM provider unavailable: [Errno 111] Connection refused"),
    ).not.toBeInTheDocument();
  });

  it("creates a session on the first question", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    await waitFor(() => {
      expect(mockedCreateSession).toHaveBeenCalled();
    });
    expect(mockedAsk.mock.calls[0][0].session_id).toBe("sess-1");
    expect(mockedAsk.mock.calls[0][0].replace_turn_id).toBeUndefined();
  });

  it("starts a new conversation without deleting the previous session", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Grounded")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "New research" }));
    expect(screen.queryByText("What is attention?")).not.toBeInTheDocument();
    expect(mockedDeleteSession).not.toHaveBeenCalled();
  });

  it("notices selected documents that left the library", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedListSessions.mockResolvedValue({
      sessions: [sessionRow({ title: "Filtered", turn_count: 1 })],
      request_id: "s1",
    });
    mockedGetSession.mockResolvedValue({
      ...sessionRow({ title: "Filtered", turn_count: 1 }),
      selected_document_ids: [],
      missing_selected_count: 1,
      turns: [
        {
          turn_id: "t1",
          sequence: 1,
          question: "What is attention?",
          answer: "Transformers use self-attention [S1].",
          grounding_status: "grounded",
          citations: [],
          sources: [],
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    render(<App />);
    expect(
      await screen.findByText("1 previously selected document is no longer in the library."),
    ).toBeInTheDocument();
  });

  it("keeps the library error distinct from an empty corpus when the API is down", async () => {
    mockedHealth.mockRejectedValue(new ApiClientError("network_error", "Could not reach the API.", 0));
    mockedList.mockRejectedValue(new ApiClientError("network_error", "Could not reach the API.", 0));
    render(<App />);
    expect(await screen.findByText(/Cannot reach the API/)).toBeInTheDocument();
    expect(
      screen.getByText("The document library could not be loaded."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Add a PDF, Markdown, or text document to start asking questions."),
    ).not.toBeInTheDocument();
  });

  it("retries a restored failed turn after refresh using the persisted id", async () => {
    const persistedTurnId = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedListSessions.mockResolvedValue({
      sessions: [sessionRow({ title: "Harry question", turn_count: 1 })],
      request_id: "s1",
    });
    mockedGetSession.mockResolvedValue({
      ...sessionRow({ title: "Harry question", turn_count: 1 }),
      selected_document_ids: [],
      missing_selected_count: 0,
      turns: [
        {
          turn_id: persistedTurnId,
          sequence: 1,
          question: "Where were Harry and Hermione married?",
          answer: "",
          grounding_status: "error",
          error_message: "LLM provider unavailable: [Errno 111] Connection refused",
          citations: [],
          sources: [],
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    mockedAsk.mockResolvedValueOnce(
      askResponse({
        question: "Where were Harry and Hermione married?",
        session_id: "sess-1",
        turn_id: persistedTurnId,
      }),
    );
    const user = userEvent.setup();
    render(<App />);
    expect(
      await screen.findByText("Where were Harry and Hermione married?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("LLM provider unavailable: [Errno 111] Connection refused"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Grounded")).toBeInTheDocument();
    expect(mockedAsk.mock.calls[0][0].replace_turn_id).toBe(persistedTurnId);
    expect(mockedAsk.mock.calls[0][0].question).toBe(
      "Where were Harry and Hermione married?",
    );
    expect(mockedAsk.mock.calls[0][0].session_id).toBe("sess-1");
    expect(mockedCreateSession).not.toHaveBeenCalled();
  });

  it("does not send a second ask when Retry is clicked twice", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    const persistedTurnId = "cccccccccccccccccccccccccccccccc";
    mockedAsk.mockRejectedValueOnce(
      new ApiClientError(
        "provider_unavailable",
        "LLM provider unavailable: [Errno 111] Connection refused",
        503,
        "r1",
        { turnId: persistedTurnId, sessionId: "sess-1" },
      ),
    );
    let finish: ((value: AskResponse) => void) | undefined;
    mockedAsk.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    const retry = await screen.findByRole("button", { name: "Retry" });
    await user.click(retry);
    expect(mockedAsk).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Working…" })).toBeDisabled();
    finish?.(askResponse({ session_id: "sess-1", turn_id: persistedTurnId }));
    expect(await screen.findByText("Grounded")).toBeInTheDocument();
  });

  it("hides Retry when the failed turn no longer exists", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    const persistedTurnId = "dddddddddddddddddddddddddddddddd";
    mockedAsk.mockRejectedValueOnce(
      new ApiClientError(
        "provider_unavailable",
        "LLM provider unavailable: [Errno 111] Connection refused",
        503,
        "r1",
        { turnId: persistedTurnId, sessionId: "sess-1" },
      ),
    );
    mockedAsk.mockRejectedValueOnce(
      new ApiClientError("not_found", "Turn not found.", 404, "r2"),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(
      await screen.findByText("LLM provider unavailable: [Errno 111] Connection refused"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Turn not found.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(screen.getByText("What is attention?")).toBeInTheDocument();
    expect(screen.queryByText("Insufficient evidence")).not.toBeInTheDocument();
  });

  it("does not label a technical ask failure as insufficient evidence", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedAsk.mockRejectedValue(
      new ApiClientError("provider_unavailable", "Language model unavailable.", 503),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Language model unavailable.")).toBeInTheDocument();
    expect(screen.queryByText("Insufficient evidence")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Research question")).toHaveValue("");
    expect(screen.getByText("What is attention?")).toBeInTheDocument();
  });

  it("disables Ask while a request is in flight", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    let finish: ((value: AskResponse) => void) | undefined;
    mockedAsk.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.type(screen.getByLabelText("Research question"), "What is attention?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByRole("button", { name: "Working…" })).toBeDisabled();
    finish?.(askResponse({ session_id: "sess-1", turn_id: "turn-1" }));
    expect(await screen.findByText("Grounded")).toBeInTheDocument();
  });

  it("shows upload too large errors from the API", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedUpload.mockRejectedValue(
      new ApiClientError("too_large", "File exceeds max size (100 bytes).", 413),
    );
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByText("attention.md");
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const huge = new File(["x"], "paper.md", { type: "text/markdown" });
    await user.upload(input, huge);
    expect(await screen.findByText("File exceeds max size (100 bytes).")).toBeInTheDocument();
  });

  it("shows unsupported upload errors from the API", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedUpload.mockRejectedValue(
      new ApiClientError("unsupported_type", "Upload content type does not match a supported document format.", 415),
    );
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByText("attention.md");
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "notes.md", { type: "text/markdown" });
    await user.upload(input, file);
    expect(
      await screen.findByText("Upload content type does not match a supported document format."),
    ).toBeInTheDocument();
  });

  it("keeps the workspace usable when session list load fails", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedListSessions.mockRejectedValue(
      new ApiClientError("network_error", "Could not load research sessions.", 0),
    );
    render(<App />);
    await screen.findByText("attention.md");
    expect(await screen.findByText("Could not load research sessions.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask question" })).toBeInTheDocument();
  });

  it("surfaces re-index failure without claiming success", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedReindex.mockRejectedValue(
      new ApiClientError("source_missing", "Source file is missing.", 409),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.click(screen.getByRole("button", { name: "Actions for attention.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Re-index" }));
    expect(await screen.findByText("Source file is missing.")).toBeInTheDocument();
    expect(screen.getByTestId("document-action-error")).toHaveTextContent(
      "Source file is missing.",
    );
    expect(screen.queryByTestId("upload-error")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("Re-indexing…")).not.toBeInTheDocument();
    });
  });

  it("opens details with filename status pages and chunks", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow({ page_count: 3, chunk_count: 8 })],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedGet.mockResolvedValue({
      ...documentRow({ page_count: 3, chunk_count: 8 }),
      chunker_id: "structure.v1:test",
      parser_id: "markdown.v1",
      warnings: [],
      checksum_sha256: "abc123def456",
      index_status: "ready",
    });
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.click(screen.getByRole("button", { name: "Actions for attention.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Details" }));
    const dialog = await screen.findByRole("dialog", { name: "attention.md" });
    expect(dialog).toHaveTextContent("Ready");
    expect(dialog).toHaveTextContent("3");
    expect(dialog).toHaveTextContent("8");
    expect(dialog).toHaveTextContent("text/markdown");
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog", { name: "attention.md" })).not.toBeInTheDocument();
  });

  it("shows a details-specific error instead of an upload error", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedGet.mockRejectedValue(
      new ApiClientError("internal_error", "An unexpected error occurred.", 500),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    await user.click(screen.getByRole("button", { name: "Actions for attention.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Details" }));
    expect(await screen.findByTestId("document-details-error")).toHaveTextContent(
      "Could not load document details.",
    );
    expect(screen.queryByTestId("upload-error")).not.toBeInTheDocument();
    expect(screen.queryByText("An unexpected error occurred.")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByTestId("document-details-error")).not.toBeInTheDocument();
  });

  it("opens details for a newly uploaded document", async () => {
    mockedUpload.mockResolvedValue({
      document: documentRow({ document_id: "doc-new", filename: "notes.md" }),
      outcome: "created",
      warnings: [],
      request_id: "u1",
    });
    mockedList.mockResolvedValueOnce({
      documents: [],
      chunker_id: "structure.v1:test",
      request_id: "d0",
    });
    mockedList.mockResolvedValue({
      documents: [documentRow({ document_id: "doc-new", filename: "notes.md" })],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedGet.mockResolvedValue({
      ...documentRow({ document_id: "doc-new", filename: "notes.md" }),
      chunker_id: "structure.v1:test",
      parser_id: "markdown.v1",
      warnings: [],
    });
    const user = userEvent.setup();
    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(["# hi"], "notes.md", { type: "text/markdown" }));
    expect(await screen.findByText("notes.md")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Actions for notes.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Details" }));
    expect(await screen.findByRole("dialog", { name: "notes.md" })).toBeInTheDocument();
    expect(mockedGet).toHaveBeenCalledWith("doc-new");
  });

  it("shows Re-indexing, blocks duplicate clicks, and refreshes on success", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow({ chunk_count: 1 })],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    let finish: ((value: {
      document: ReturnType<typeof documentRow>;
      outcome: string;
      warnings: string[];
      request_id: string;
    }) => void) | undefined;
    mockedReindex.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("attention.md");
    const selected = screen.getByRole("checkbox", { name: /attention.md/ });
    expect(selected).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Actions for attention.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Re-index" }));
    expect(await screen.findByText("Re-indexing…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Actions for attention.md" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /attention.md/ })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Actions for attention.md" }));
    expect(mockedReindex).toHaveBeenCalledTimes(1);
    mockedList.mockResolvedValue({
      documents: [documentRow({ chunk_count: 4, warning_count: 1 })],
      chunker_id: "structure.v1:test",
      request_id: "d2",
    });
    finish?.({
      document: documentRow({ chunk_count: 4, warning_count: 1 }),
      outcome: "updated",
      warnings: ["unclosed_code_fence"],
      request_id: "r1",
    });
    expect(await screen.findByText("4 chunks")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("Re-indexing…")).not.toBeInTheDocument();
    });
    expect(screen.getByText("1 warnings")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /attention.md/ })).toBeChecked();
  });

  it("keeps a failed re-index from looking like success and leaves Remove working", async () => {
    mockedList.mockResolvedValue({
      documents: [
        documentRow(),
        documentRow({ document_id: "doc-2", filename: "other.md" }),
      ],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedReindex.mockRejectedValue(
      new ApiClientError("indexing_error", "Indexing failed.", 500),
    );
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("other.md");
    mockedList.mockResolvedValue({
      documents: [
        documentRow({ status: "failed", error_message: "Indexing failed." }),
        documentRow({ document_id: "doc-2", filename: "other.md" }),
      ],
      chunker_id: "structure.v1:test",
      request_id: "d2",
    });
    await user.click(screen.getByRole("button", { name: "Actions for attention.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Re-index" }));
    expect(await screen.findByTestId("document-action-error")).toHaveTextContent(
      "Indexing failed.",
    );
    expect(screen.queryByTestId("upload-error")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByTestId("document-card")[0]).toHaveTextContent("Failed");
    });
    expect(screen.getAllByTestId("document-card")[0]).not.toHaveTextContent("Ready");
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Actions for other.md" })).not.toBeDisabled();
    });
    mockedDelete.mockResolvedValue({
      document_id: "doc-2",
      deleted: true,
      already_absent: false,
      vector_cleanup_status: "purged",
      request_id: "x",
    });
    mockedList.mockResolvedValue({
      documents: [documentRow({ status: "failed", error_message: "Indexing failed." })],
      chunker_id: "structure.v1:test",
      request_id: "d3",
    });
    await user.click(screen.getByRole("button", { name: "Actions for other.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Remove" }));
    await user.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => {
      expect(mockedDelete).toHaveBeenCalledWith("doc-2");
    });
    await waitFor(() => {
      expect(screen.queryByText("other.md")).not.toBeInTheDocument();
    });
  });

  it("keeps upload errors in the upload scope after a document action", async () => {
    mockedList.mockResolvedValue({
      documents: [documentRow()],
      chunker_id: "structure.v1:test",
      request_id: "d1",
    });
    mockedUpload.mockRejectedValue(
      new ApiClientError("unsupported_type", "Unsupported file type.", 415),
    );
    mockedGet.mockRejectedValue(
      new ApiClientError("internal_error", "An unexpected error occurred.", 500),
    );
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByText("attention.md");
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(input, new File(["x"], "notes.md", { type: "text/markdown" }));
    expect(await screen.findByTestId("upload-error")).toHaveTextContent("Unsupported file type.");
    await user.click(screen.getByRole("button", { name: "Actions for attention.md" }));
    await user.click(screen.getByRole("menuitem", { name: "Details" }));
    expect(await screen.findByTestId("document-details-error")).toHaveTextContent(
      "Could not load document details.",
    );
    expect(screen.getByTestId("upload-error")).toHaveTextContent("Unsupported file type.");
  });

  describe("document drop and selection", () => {
    function pdfFile(name = "paper.pdf"): File {
      return new File(["%PDF-1.4"], name, { type: "application/pdf" });
    }

    function fileDrag(files: File[], extra: Record<string, unknown> = {}) {
      return {
        dataTransfer: {
          types: ["Files"],
          files,
          items: files,
          dropEffect: "none",
          effectAllowed: "copy",
        },
        ...extra,
      };
    }

    function expectDropOverlay(visible: boolean) {
      const overlay = screen.getByTestId("drop-overlay");
      expect(overlay).toHaveTextContent("Drop files to add them");
      if (visible) {
        expect(overlay).toHaveClass("is-active");
        expect(overlay).toHaveAttribute("aria-hidden", "false");
      } else {
        expect(overlay).not.toHaveClass("is-active");
        expect(overlay).toHaveAttribute("aria-hidden", "true");
      }
      expect(screen.getByTestId("app-shell")).toContainElement(
        screen.getByRole("heading", { name: "Research Assistant" }),
      );
    }

    async function renderLibrary(docs: ReturnType<typeof documentRow>[] = [documentRow()]) {
      mockedList.mockResolvedValue({
        documents: docs,
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedUpload.mockResolvedValue({
        document: documentRow({ document_id: "doc-new", filename: "paper.pdf" }),
        outcome: "created",
        warnings: [],
        request_id: "u1",
      });
      const user = userEvent.setup();
      render(<App />);
      await screen.findByText(docs[0].filename);
      return user;
    }

    it("shows drop feedback while a valid file is dragged over the app", async () => {
      await renderLibrary();
      const shell = screen.getByTestId("app-shell");
      fireEvent.dragEnter(shell, fileDrag([pdfFile()]));
      expectDropOverlay(true);
    });

    it("hides drop feedback when the drag leaves the app", async () => {
      await renderLibrary();
      const shell = screen.getByTestId("app-shell");
      fireEvent.dragEnter(shell, fileDrag([pdfFile()]));
      expectDropOverlay(true);
      fireEvent.dragLeave(shell, fileDrag([pdfFile()]));
      expectDropOverlay(false);
    });

    it("uploads a dropped PDF through the existing upload path once", async () => {
      await renderLibrary();
      fireEvent.drop(screen.getByTestId("app-shell"), fileDrag([pdfFile()]));
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(1);
      });
      expect(mockedUpload.mock.calls[0][0].name).toBe("paper.pdf");
    });

    it("uploads dropped Markdown and text through the same path", async () => {
      await renderLibrary();
      fireEvent.drop(
        screen.getByTestId("app-shell"),
        fileDrag([new File(["# hi"], "notes.md", { type: "text/markdown" })]),
      );
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(1);
      });
      mockedUpload.mockClear();
      fireEvent.drop(
        screen.getByTestId("app-shell"),
        fileDrag([new File(["hi"], "notes.txt", { type: "text/plain" })]),
      );
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(1);
      });
    });

    it("rejects PNG and JPEG drops without uploading", async () => {
      await renderLibrary();
      fireEvent.drop(
        screen.getByTestId("app-shell"),
        fileDrag([new File(["img"], "photo.png", { type: "image/png" })]),
      );
      expect(
        await screen.findByText("Unsupported file type. Add a PDF, Markdown, or text file."),
      ).toBeInTheDocument();
      expect(mockedUpload).not.toHaveBeenCalled();
      fireEvent.drop(
        screen.getByTestId("app-shell"),
        fileDrag([new File(["img"], "photo.jpg", { type: "image/jpeg" })]),
      );
      expect(mockedUpload).not.toHaveBeenCalled();
    });

    it("prevents the browser default drop behavior", async () => {
      await renderLibrary();
      const shell = screen.getByTestId("app-shell");
      const event = createEvent.drop(shell, fileDrag([pdfFile()]));
      fireEvent(shell, event);
      expect(event.defaultPrevented).toBe(true);
    });

    it("does not flicker the overlay on nested dragenter/dragleave", async () => {
      await renderLibrary();
      const shell = screen.getByTestId("app-shell");
      const inner = screen.getByRole("heading", { name: "Documents" });
      fireEvent.dragEnter(shell, fileDrag([pdfFile()]));
      fireEvent.dragEnter(inner, fileDrag([pdfFile()], { relatedTarget: inner }));
      expectDropOverlay(true);
      fireEvent.dragLeave(inner, fileDrag([pdfFile()], { relatedTarget: shell }));
      expectDropOverlay(true);
      fireEvent.dragLeave(shell, fileDrag([pdfFile()]));
      expectDropOverlay(false);
    });

    it("recovers after a cancelled drag without a page reload", async () => {
      await renderLibrary();
      const shell = screen.getByTestId("app-shell");
      fireEvent.dragEnter(shell, fileDrag([pdfFile()]));
      expectDropOverlay(true);
      fireEvent.blur(window);
      expectDropOverlay(false);
      fireEvent.dragEnter(shell, fileDrag([pdfFile()]));
      expectDropOverlay(true);
      fireEvent.drop(shell, fileDrag([pdfFile()]));
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(1);
      });
      expectDropOverlay(false);
    });

    it("hides the overlay after an unsupported drop and keeps the shell mounted", async () => {
      await renderLibrary();
      const shell = screen.getByTestId("app-shell");
      fireEvent.dragEnter(shell, fileDrag([pdfFile()]));
      expectDropOverlay(true);
      fireEvent.drop(
        shell,
        fileDrag([new File(["img"], "photo.png", { type: "image/png" })]),
      );
      expectDropOverlay(false);
      expect(shell).toBe(screen.getByTestId("app-shell"));
      expect(mockedUpload).not.toHaveBeenCalled();
    });

    it("does not upload twice for a single drop", async () => {
      await renderLibrary();
      const shell = screen.getByTestId("app-shell");
      fireEvent.drop(shell, fileDrag([pdfFile()]));
      fireEvent.drop(shell, fileDrag([pdfFile()]));
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(1);
      });
    });

    it("shows the uploaded document without a generic error", async () => {
      await renderLibrary();
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-new", filename: "paper.pdf" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d2",
      });
      fireEvent.drop(screen.getByTestId("app-shell"), fileDrag([pdfFile()]));
      expect(await screen.findByText("paper.pdf")).toBeInTheDocument();
      expect(screen.queryByText("An unexpected error occurred.")).not.toBeInTheDocument();
    });

    it("keeps a successful upload when library refresh fails", async () => {
      await renderLibrary();
      mockedList.mockRejectedValue(
        new ApiClientError("network_error", "Could not reach the API. Is the backend running?", 0),
      );
      fireEvent.drop(screen.getByTestId("app-shell"), fileDrag([pdfFile()]));
      expect(await screen.findByText("paper.pdf")).toBeInTheDocument();
      expect(
        await screen.findByText(
          "Document uploaded, but the library could not be refreshed. Retry loading the library.",
        ),
      ).toBeInTheDocument();
      expect(screen.queryByText("An unexpected error occurred.")).not.toBeInTheDocument();
    });

    it("does not show an upload failure when the document is already in the library", async () => {
      await renderLibrary();
      mockedUpload.mockRejectedValue(
        new ApiClientError("internal_error", "An unexpected error occurred.", 500),
      );
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-new", filename: "paper.pdf", status: "ready" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d2",
      });
      fireEvent.drop(screen.getByTestId("app-shell"), fileDrag([pdfFile()]));
      expect(await screen.findByText("paper.pdf")).toBeInTheDocument();
      expect(screen.queryByText("An unexpected error occurred.")).not.toBeInTheDocument();
      expect(screen.queryByText(/Upload failed/)).not.toBeInTheDocument();
    });

    it("maps an unconfirmed upload failure to a specific message", async () => {
      await renderLibrary();
      mockedUpload.mockRejectedValue(
        new ApiClientError("internal_error", "An unexpected error occurred.", 500),
      );
      fireEvent.drop(screen.getByTestId("app-shell"), fileDrag([pdfFile()]));
      expect(
        await screen.findByText("Upload failed. The server did not confirm the result."),
      ).toBeInTheDocument();
      expect(screen.queryByText("paper.pdf")).not.toBeInTheDocument();
    });

    it("hides overlay after nested leave with no relatedTarget, then allows another drag", async () => {
      await renderLibrary();
      const shell = screen.getByTestId("app-shell");
      const inner = screen.getByRole("heading", { name: "Documents" });
      fireEvent.dragEnter(shell, fileDrag([pdfFile()]));
      expectDropOverlay(true);
      fireEvent.dragLeave(inner, fileDrag([pdfFile()], { relatedTarget: null }));
      await waitFor(() => {
        expect(screen.getByTestId("drop-overlay")).not.toHaveClass("is-active");
      });
      fireEvent.dragEnter(shell, fileDrag([pdfFile()]));
      expectDropOverlay(true);
    });

    it("still uploads through Add document file picker", async () => {
      const user = await renderLibrary();
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(input, pdfFile("picker.pdf"));
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(1);
      });
      expect(mockedUpload.mock.calls[0][0].name).toBe("picker.pdf");
    });

    it("uploads multiple files through Add documents picker", async () => {
      const user = await renderLibrary();
      mockedUpload
        .mockResolvedValueOnce({
          document: documentRow({ document_id: "doc-a", filename: "a.pdf" }),
          outcome: "created",
          warnings: [],
          request_id: "u1",
        })
        .mockResolvedValueOnce({
          document: documentRow({ document_id: "doc-b", filename: "b.pdf" }),
          outcome: "created",
          warnings: [],
          request_id: "u2",
        });
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-a", filename: "a.pdf" }),
          documentRow({ document_id: "doc-b", filename: "b.pdf" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d2",
      });
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      expect(input).toHaveAttribute("multiple");
      await user.upload(input, [pdfFile("a.pdf"), pdfFile("b.pdf")]);
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(2);
      });
      expect(mockedUpload.mock.calls[0][0].name).toBe("a.pdf");
      expect(mockedUpload.mock.calls[1][0].name).toBe("b.pdf");
      expect(await screen.findByText("a.pdf")).toBeInTheDocument();
      expect(screen.getByText("b.pdf")).toBeInTheDocument();
      expect(await screen.findByTestId("upload-status")).toHaveTextContent("2 documents added.");
    });

    it("uploads mixed PDF, Markdown, and text in one picker batch", async () => {
      const user = await renderLibrary();
      mockedUpload.mockImplementation(async (file: File) => ({
        document: documentRow({ document_id: `id-${file.name}`, filename: file.name }),
        outcome: "created",
        warnings: [],
        request_id: "u",
      }));
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "id-paper.pdf", filename: "paper.pdf" }),
          documentRow({ document_id: "id-notes.md", filename: "notes.md" }),
          documentRow({ document_id: "id-summary.txt", filename: "summary.txt" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d2",
      });
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(input, [
        pdfFile("paper.pdf"),
        new File(["# n"], "notes.md", { type: "text/markdown" }),
        new File(["t"], "summary.txt", { type: "text/plain" }),
      ]);
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(3);
      });
    });

    it("drops multiple supported files", async () => {
      await renderLibrary();
      mockedUpload.mockImplementation(async (file: File) => ({
        document: documentRow({ document_id: `id-${file.name}`, filename: file.name }),
        outcome: "created",
        warnings: [],
        request_id: "u",
      }));
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "id-a.pdf", filename: "a.pdf" }),
          documentRow({ document_id: "id-b.pdf", filename: "b.pdf" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d2",
      });
      fireEvent.drop(
        screen.getByTestId("app-shell"),
        fileDrag([pdfFile("a.pdf"), pdfFile("b.pdf")]),
      );
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(2);
      });
      expect(await screen.findByText("a.pdf")).toBeInTheDocument();
    });

    it("keeps valid files when a drop also includes an unsupported type", async () => {
      await renderLibrary();
      mockedUpload.mockResolvedValue({
        document: documentRow({ document_id: "doc-ok", filename: "ok.pdf" }),
        outcome: "created",
        warnings: [],
        request_id: "u1",
      });
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-ok", filename: "ok.pdf" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d2",
      });
      fireEvent.drop(
        screen.getByTestId("app-shell"),
        fileDrag([
          pdfFile("ok.pdf"),
          new File(["img"], "photo.png", { type: "image/png" }),
        ]),
      );
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(1);
      });
      expect(mockedUpload.mock.calls[0][0].name).toBe("ok.pdf");
      expect(await screen.findByText("ok.pdf")).toBeInTheDocument();
      expect(await screen.findByTestId("upload-error")).toHaveTextContent("photo.png");
      expect(screen.getByTestId("upload-error")).toHaveTextContent(UNSUPPORTED_UPLOAD_MESSAGE);
    });

    it("continues a later valid file after an invalid PDF", async () => {
      await renderLibrary();
      mockedUpload
        .mockRejectedValueOnce(
          new ApiClientError("invalid_pdf", "The file is not a valid PDF.", 400),
        )
        .mockResolvedValueOnce({
          document: documentRow({ document_id: "doc-ok", filename: "ok.md" }),
          outcome: "created",
          warnings: [],
          request_id: "u2",
        });
      mockedList
        .mockResolvedValueOnce({
          documents: [documentRow()],
          chunker_id: "structure.v1:test",
          request_id: "d-mid",
        })
        .mockResolvedValue({
          documents: [
            documentRow(),
            documentRow({ document_id: "doc-ok", filename: "ok.md" }),
          ],
          chunker_id: "structure.v1:test",
          request_id: "d2",
        });
      fireEvent.drop(
        screen.getByTestId("app-shell"),
        fileDrag([
          pdfFile("fake.pdf"),
          new File(["# ok"], "ok.md", { type: "text/markdown" }),
        ]),
      );
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(2);
      });
      expect(await screen.findByText("ok.md")).toBeInTheDocument();
      expect(screen.queryByText("fake.pdf")).not.toBeInTheDocument();
      expect(await screen.findByTestId("upload-error")).toHaveTextContent("fake.pdf");
    });

    it("rejects an all-invalid batch without calling upload", async () => {
      await renderLibrary();
      fireEvent.drop(
        screen.getByTestId("app-shell"),
        fileDrag([new File(["img"], "photo.png", { type: "image/png" })]),
      );
      expect(await screen.findByTestId("upload-error")).toHaveTextContent(
        "Unsupported file type. Add a PDF, Markdown, or text file.",
      );
      expect(mockedUpload).not.toHaveBeenCalled();
    });

    it("allows a second batch after the first completes", async () => {
      await renderLibrary();
      mockedUpload.mockResolvedValue({
        document: documentRow({ document_id: "doc-a", filename: "a.pdf" }),
        outcome: "created",
        warnings: [],
        request_id: "u1",
      });
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-a", filename: "a.pdf" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d2",
      });
      fireEvent.drop(screen.getByTestId("app-shell"), fileDrag([pdfFile("a.pdf")]));
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(1);
      });
      mockedUpload.mockResolvedValue({
        document: documentRow({ document_id: "doc-b", filename: "b.pdf" }),
        outcome: "created",
        warnings: [],
        request_id: "u2",
      });
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-a", filename: "a.pdf" }),
          documentRow({ document_id: "doc-b", filename: "b.pdf" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d3",
      });
      fireEvent.drop(screen.getByTestId("app-shell"), fileDrag([pdfFile("b.pdf")]));
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalledTimes(2);
      });
      expect(await screen.findByText("b.pdf")).toBeInTheDocument();
    });

    it("dismisses an upload error without a refresh", async () => {
      const user = await renderLibrary();
      mockedUpload.mockRejectedValue(
        new ApiClientError("invalid_pdf", "The file is not a valid PDF.", 400),
      );
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      await user.upload(input, pdfFile("broken.pdf"));
      expect(await screen.findByText("The file is not a valid PDF.")).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Dismiss upload message" }));
      expect(screen.queryByTestId("upload-error")).not.toBeInTheDocument();
    });

    it("treats the master checkbox as a derived select-all control", async () => {
      const user = await renderLibrary([
        documentRow(),
        documentRow({ document_id: "doc-2", filename: "other.md" }),
      ]);
      const master = screen.getByRole("checkbox", { name: "Ask across all documents" });
      expect(master).toBeChecked();
      await user.click(master);
      expect(master).not.toBeChecked();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).not.toBeChecked();
      expect(screen.getByRole("checkbox", { name: /other.md/ })).not.toBeChecked();
      await user.click(master);
      expect(master).toBeChecked();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: /other.md/ })).toBeChecked();
    });

    it("sets the master checkbox indeterminate for a partial selection", async () => {
      const user = await renderLibrary([
        documentRow(),
        documentRow({ document_id: "doc-2", filename: "other.md" }),
      ]);
      await user.click(screen.getByText("other.md"));
      const master = screen.getByRole("checkbox", { name: "Ask across all documents" });
      expect(master).toHaveProperty("indeterminate", true);
      expect(master).toHaveAttribute("aria-checked", "mixed");
      await user.click(master);
      expect(master).toBeChecked();
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).toBeChecked();
      expect(screen.getByRole("checkbox", { name: /other.md/ })).toBeChecked();
    });

    it("disables Ask and explains when no document is selected", async () => {
      const user = await renderLibrary([
        documentRow(),
        documentRow({ document_id: "doc-2", filename: "other.md" }),
      ]);
      await user.click(screen.getByRole("checkbox", { name: "Ask across all documents" }));
      const ask = screen.getByRole("button", { name: "Ask question" });
      expect(ask).toBeDisabled();
      expect(
        screen.getAllByText("Select at least one document to ask a question.").length,
      ).toBeGreaterThan(0);
      await user.type(screen.getByLabelText("Research question"), "What is attention?");
      expect(ask).toBeDisabled();
      expect(mockedAsk).not.toHaveBeenCalled();
      await user.click(screen.getByText("attention.md"));
      expect(ask).not.toBeDisabled();
      await user.click(ask);
      await waitFor(() => {
        expect(mockedAsk).toHaveBeenCalled();
      });
      expect(mockedAsk.mock.calls[0][0].document_ids).toEqual(["doc-1"]);
    });

    it("does not restore all-document selection after a document list refresh", async () => {
      const user = await renderLibrary([
        documentRow(),
        documentRow({ document_id: "doc-2", filename: "other.md" }),
      ]);
      await user.click(screen.getByRole("checkbox", { name: "Ask across all documents" }));
      expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();
      mockedList.mockResolvedValue({
        documents: [
          documentRow(),
          documentRow({ document_id: "doc-2", filename: "other.md" }),
        ],
        chunker_id: "structure.v1:test",
        request_id: "d2",
      });
      await user.upload(
        document.querySelector('input[type="file"]') as HTMLInputElement,
        pdfFile("refresh.pdf"),
      );
      await waitFor(() => {
        expect(mockedUpload).toHaveBeenCalled();
      });
      expect(screen.getByRole("checkbox", { name: /attention.md/ })).not.toBeChecked();
      expect(screen.getByRole("checkbox", { name: /other.md/ })).not.toBeChecked();
    });
  });

  describe("conversation viewport", () => {
    const VIEWPORT = 480;
    const TURN_HEIGHT = 140;
    const GAP = 24;
    let restoreGeometry: (() => void) | undefined;

    function layoutRect(top: number, height: number): DOMRect {
      return {
        x: 0,
        y: top,
        width: 720,
        height,
        top,
        left: 0,
        bottom: top + height,
        right: 720,
        toJSON() {
          return {};
        },
      };
    }

    function installConversationGeometry() {
      const elementProto = HTMLElement.prototype;
      const clientDesc =
        Object.getOwnPropertyDescriptor(Element.prototype, "clientHeight") ??
        Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientHeight");
      const scrollDesc =
        Object.getOwnPropertyDescriptor(Element.prototype, "scrollHeight") ??
        Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollHeight");
      const pad = 12;

      vi.spyOn(elementProto, "getBoundingClientRect").mockImplementation(function (
        this: HTMLElement,
      ) {
        if (this.getAttribute("data-testid") === "conversation-scroll") {
          return layoutRect(0, VIEWPORT);
        }
        if (this.classList.contains("turn")) {
          const pane = this.closest("[data-testid='conversation-scroll']");
          const index = this.parentElement
            ? [...this.parentElement.querySelectorAll("li.turn")].indexOf(this)
            : 0;
          const top = pad + index * (TURN_HEIGHT + GAP) - (pane?.scrollTop ?? 0);
          return layoutRect(top, TURN_HEIGHT);
        }
        return layoutRect(0, 0);
      });

      Object.defineProperty(Element.prototype, "clientHeight", {
        configurable: true,
        get(this: Element) {
          if (this.getAttribute("data-testid") === "conversation-scroll") {
            return VIEWPORT;
          }
          return clientDesc?.get?.call(this) ?? 0;
        },
      });
      Object.defineProperty(Element.prototype, "scrollHeight", {
        configurable: true,
        get(this: Element) {
          if (this.getAttribute("data-testid") === "conversation-scroll") {
            const n = this.querySelectorAll("li.turn").length;
            const spacer = this.querySelector(
              "[data-testid='conversation-follow-space']",
            ) as HTMLElement | null;
            const spacerH = Number.parseFloat(spacer?.style.height || "0") || 0;
            return pad + n * (TURN_HEIGHT + GAP) + spacerH + 48;
          }
          return scrollDesc?.get?.call(this) ?? 0;
        },
      });

      return () => {
        vi.mocked(elementProto.getBoundingClientRect).mockRestore();
        if (clientDesc) {
          Object.defineProperty(Element.prototype, "clientHeight", clientDesc);
        }
        if (scrollDesc) {
          Object.defineProperty(Element.prototype, "scrollHeight", scrollDesc);
        }
      };
    }

    function sessionTurn(
      overrides: Partial<SessionTurnView> &
        Pick<SessionTurnView, "turn_id" | "sequence" | "question">,
    ): SessionTurnView {
      return {
        answer: "Prior answer.",
        grounding_status: "grounded",
        citations: [],
        sources: [],
        created_at: "2026-01-01T00:00:00Z",
        ...overrides,
      };
    }

    function longSessionTurns(count: number): SessionTurnView[] {
      return Array.from({ length: count }, (_, index) =>
        sessionTurn({
          turn_id: `turn-${String(index + 1).padStart(2, "0")}`,
          sequence: index + 1,
          question: `Prior question ${index + 1}`,
          answer: `Prior answer ${index + 1}.`,
        }),
      );
    }

    function lastTurn(pane: HTMLElement): HTMLElement {
      const turn = pane.querySelector("li.turn:last-child");
      if (!(turn instanceof HTMLElement)) {
        throw new Error("expected a conversation turn");
      }
      return turn;
    }

    function expectTurnNearTop(pane: HTMLElement, turn: HTMLElement) {
      const offset = turn.getBoundingClientRect().top - pane.getBoundingClientRect().top;
      expect(offset).toBe(TURN_TOP_PAD);
      expect(turnIsVisibleInPane(pane, turn)).toBe(true);
    }

    async function renderLongConversation(turns: SessionTurnView[] = longSessionTurns(8)) {
      mockedList.mockResolvedValue({
        documents: [documentRow()],
        chunker_id: "structure.v1:test",
        request_id: "d1",
      });
      mockedListSessions.mockResolvedValue({
        sessions: [sessionRow({ title: "Long thread", turn_count: turns.length })],
        request_id: "s1",
      });
      mockedGetSession.mockResolvedValue({
        ...sessionRow({ title: "Long thread", turn_count: turns.length }),
        selected_document_ids: ["doc-1"],
        missing_selected_count: 0,
        turns,
      });
      const user = userEvent.setup();
      render(<App />);
      expect(await screen.findByText(turns[0].question)).toBeInTheDocument();
      return user;
    }

    beforeEach(() => {
      restoreGeometry = installConversationGeometry();
    });

    afterEach(() => {
      restoreGeometry?.();
      restoreGeometry = undefined;
    });

    it("A: submitting from the top brings the new user turn near the top", async () => {
      const user = await renderLongConversation();
      const pane = screen.getByTestId("conversation-scroll");
      pane.scrollTop = 0;
      expect(lastTurn(pane).getBoundingClientRect().top).toBeGreaterThan(VIEWPORT);
      await user.type(screen.getByLabelText("Research question"), "What is attention?");
      await user.click(screen.getByRole("button", { name: "Ask question" }));
      expect(await screen.findByText("What is attention?")).toBeInTheDocument();
      await waitFor(() => {
        expectTurnNearTop(pane, lastTurn(pane));
      });
      expect(lastTurn(pane)).toHaveAttribute("data-turn-id");
      expect(Number.parseFloat(screen.getByTestId("conversation-follow-space").style.height)).toBeGreaterThan(
        0,
      );
    });

    it("B: submitting from halfway up brings the new user turn near the top", async () => {
      const user = await renderLongConversation();
      const pane = screen.getByTestId("conversation-scroll");
      pane.scrollTop = Math.floor((pane.scrollHeight - pane.clientHeight) / 2);
      const halfway = pane.scrollTop;
      expect(halfway).toBeGreaterThan(0);
      await user.type(screen.getByLabelText("Research question"), "What is attention?");
      await user.click(screen.getByRole("button", { name: "Ask question" }));
      expect(await screen.findByText("What is attention?")).toBeInTheDocument();
      await waitFor(() => {
        expectTurnNearTop(pane, lastTurn(pane));
      });
      expect(pane.scrollTop).not.toBe(halfway);
    });

    it("C: submitting while already at the bottom still pins the new turn near the top", async () => {
      const user = await renderLongConversation();
      const pane = screen.getByTestId("conversation-scroll");
      pane.scrollTop = pane.scrollHeight - pane.clientHeight;
      expect(pane.scrollTop).toBeGreaterThan(0);
      await user.type(screen.getByLabelText("Research question"), "What is attention?");
      await user.click(screen.getByRole("button", { name: "Ask question" }));
      expect(await screen.findByText("What is attention?")).toBeInTheDocument();
      await waitFor(() => {
        expectTurnNearTop(pane, lastTurn(pane));
      });
    });

    it("D: the new question stays visible while Working is shown", async () => {
      let finish: ((value: AskResponse) => void) | undefined;
      mockedAsk.mockImplementation(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      );
      const user = await renderLongConversation();
      const pane = screen.getByTestId("conversation-scroll");
      pane.scrollTop = 0;
      await user.type(screen.getByLabelText("Research question"), "What is attention?");
      await user.click(screen.getByRole("button", { name: "Ask question" }));
      expect(await screen.findByText("What is attention?")).toBeInTheDocument();
      expect(screen.getAllByText("Working…").length).toBeGreaterThan(0);
      await waitFor(() => {
        expectTurnNearTop(pane, lastTurn(pane));
      });
      finish?.(askResponse({ session_id: "sess-1", turn_id: "turn-new" }));
      expect(await screen.findByText(/Transformers use self-attention/)).toBeInTheDocument();
      expectTurnNearTop(pane, lastTurn(pane));
    });

    it("E: scrolling up during generation is not yanked back by the answer", async () => {
      let finish: ((value: AskResponse) => void) | undefined;
      mockedAsk.mockImplementation(
        () =>
          new Promise((resolve) => {
            finish = resolve;
          }),
      );
      const user = await renderLongConversation();
      const pane = screen.getByTestId("conversation-scroll");
      await user.type(screen.getByLabelText("Research question"), "What is attention?");
      await user.click(screen.getByRole("button", { name: "Ask question" }));
      await waitFor(() => {
        expectTurnNearTop(pane, lastTurn(pane));
      });
      pane.scrollTop = 40;
      fireEvent.scroll(pane);
      finish?.(askResponse({ session_id: "sess-1", turn_id: "turn-new" }));
      expect(await screen.findByText(/Transformers use self-attention/)).toBeInTheDocument();
      expect(pane.scrollTop).toBe(40);
    });

    it("F: retrying an off-screen failed turn brings it into view", async () => {
      const turns = longSessionTurns(8);
      turns[7] = sessionTurn({
        turn_id: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        sequence: 8,
        question: "Where were Harry and Hermione married?",
        answer: "",
        grounding_status: "error",
        error_message: "LLM provider unavailable: [Errno 111] Connection refused",
      });
      mockedAsk.mockResolvedValueOnce(
        askResponse({
          question: "Where were Harry and Hermione married?",
          session_id: "sess-1",
          turn_id: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        }),
      );
      const user = await renderLongConversation(turns);
      const pane = screen.getByTestId("conversation-scroll");
      pane.scrollTop = 0;
      expect(
        pane.querySelector('[data-turn-id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]'),
      ).toBeInstanceOf(HTMLElement);
      expect(
        (
          pane.querySelector(
            '[data-turn-id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]',
          ) as HTMLElement
        ).getBoundingClientRect().top,
      ).toBeGreaterThan(VIEWPORT);
      await user.click(screen.getByRole("button", { name: "Retry" }));
      await waitFor(() => {
        const retried = pane.querySelector(
          '[data-turn-id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]',
        ) as HTMLElement;
        expectTurnNearTop(pane, retried);
      });
      expect(await screen.findByText(/Transformers use self-attention/)).toBeInTheDocument();
    });

    it("G: a passive developer-details toggle does not move the reading position", async () => {
      const user = await renderLongConversation();
      const pane = screen.getByTestId("conversation-scroll");
      pane.scrollTop = 160;
      await user.click(screen.getByRole("button", { name: "Developer details" }));
      expect(screen.getByLabelText("Retrieval mode")).toBeInTheDocument();
      expect(pane.scrollTop).toBe(160);
    });

    it("H: session restore does not jump the viewport to the latest turn", async () => {
      await renderLongConversation();
      const pane = screen.getByTestId("conversation-scroll");
      expect(pane.scrollTop).toBe(0);
      expect(lastTurn(pane).getBoundingClientRect().top).toBeGreaterThan(VIEWPORT);
      expect(Number.parseFloat(screen.getByTestId("conversation-follow-space").style.height) || 0).toBe(
        0,
      );
    });
  });
});
