export type DocumentStatus = "failed" | "parsed" | "chunked" | "ready";

export type GroundingStatus =
  | "grounded"
  | "insufficient_evidence"
  | "unverified"
  | "invalid_citation"
  | "malformed_output";

export type RetrievalMode = "hybrid" | "dense" | "lexical";

export type HealthStatus = "ok" | "unavailable" | "not_configured" | "configured";

export type ComponentHealth = {
  status: HealthStatus;
  detail: string;
};

export type HealthResponse = {
  status: "ok";
  service: string;
  request_id: string;
};

export type ReadyResponse = {
  status: "ready" | "degraded" | "not_ready";
  database: ComponentHealth;
  vector_store: ComponentHealth;
  llm_provider: ComponentHealth;
  embedding: ComponentHealth;
  request_id: string;
};

export type DocumentSummary = {
  document_id: string;
  filename: string;
  content_type: string;
  status: DocumentStatus;
  page_count: number | null;
  chunk_count: number;
  byte_size: number;
  warning_count: number;
  ingested_at: string;
  updated_at: string;
  parse_status: string;
  error_message: string | null;
  source_available?: boolean;
  checksum_prefix?: string;
};

export type DocumentDetail = DocumentSummary & {
  chunker_id: string;
  parser_id: string | null;
  warnings: string[];
  checksum_sha256?: string;
  index_status?: string | null;
};

export type DocumentListResponse = {
  documents: DocumentSummary[];
  chunker_id: string;
  request_id: string;
};

export type UploadResponse = {
  document: DocumentSummary;
  outcome: string;
  warnings: string[];
  request_id: string;
};

export type DeleteDocumentResponse = {
  document_id: string;
  deleted: boolean;
  already_absent: boolean;
  vector_cleanup_status: string;
  request_id: string;
};

export type SourceView = {
  citation_id: string;
  filename: string;
  document_id: string;
  page_start: number | null;
  page_end: number | null;
  section_path: string[];
  locator: string;
  text: string;
  truncated: boolean;
  cited_by_model: boolean;
};

export type CitationView = {
  citation_id: string;
  filename: string;
  document_id: string;
  page_start: number | null;
  page_end: number | null;
  section_path: string[];
  locator: string;
  occurrence_count: number;
};

export type CandidateView = {
  chunk_id: string;
  document_id: string;
  filename: string;
  rank: number;
  page_start: number | null;
  page_end: number | null;
  section_path: string[];
  dense_rank: number | null;
  lexical_rank: number | null;
  rerank_rank: number | null;
  retrievers: string[];
  rerank_score: number | null;
  selected_in_context: boolean;
  context_position: number | null;
  score_note: string;
};

export type ConversationTurnPayload = {
  question: string;
  answer: string;
  grounding_status?: string;
};

export type DiagnosticsView = {
  retrieval_mode: string;
  rerank_enabled: boolean;
  candidate_count: number;
  context_source_count: number;
  dense_ms: number | null;
  lexical_ms: number | null;
  fusion_ms: number | null;
  retrieval_ms: number | null;
  rerank_ms: number | null;
  generation_ms: number | null;
  first_pass_generation_ms?: number | null;
  repair_ms?: number | null;
  llm_id: string | null;
  reranker_id: string | null;
  validation_status: string;
  candidates: CandidateView[];
  original_question?: string | null;
  retrieval_query?: string | null;
  rewrite_applied?: boolean;
  followup_detected?: boolean;
  ambiguous_followup?: boolean;
  history_turns_used?: number;
  resolver_id?: string | null;
  resolver_method?: string | null;
  resolver_ms?: number | null;
  conversation_subjects?: string[];
  repair_attempts?: number;
  generation_question?: string | null;
  context_citation_ids?: string[];
  insufficient_evidence?: boolean;
  parsed_inline_citation_ids?: string[];
  validated_citation_ids?: string[];
  structured_citation_ids?: string[];
  prompt_version?: string | null;
  parser_version?: string | null;
  generation_protocol_status?: string | null;
  parser_mode?: string | null;
  normalization_applied?: string[];
  raw_output_category?: string | null;
  format_repair_attempted?: boolean;
  format_repair_succeeded?: boolean;
};

export type AskRequest = {
  question: string;
  document_ids?: string[];
  retrieval_mode?: RetrievalMode;
  rerank?: boolean;
  conversation?: ConversationTurnPayload[];
  session_id?: string;
  replace_turn_id?: string;
};

export type AskResponse = {
  question: string;
  answer: string;
  grounding_status: GroundingStatus;
  validation_status: string;
  insufficient_evidence: boolean;
  citations: CitationView[];
  sources: SourceView[];
  diagnostics: DiagnosticsView;
  request_id: string;
  session_id?: string | null;
  turn_id?: string | null;
};

export type SessionSummary = {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turn_count: number;
  all_documents: boolean;
};

export type SessionTurnView = {
  turn_id: string;
  sequence: number;
  question: string;
  answer: string;
  grounding_status: string;
  validation_status?: string | null;
  insufficient_evidence?: boolean;
  error_message?: string | null;
  original_question?: string | null;
  retrieval_query?: string | null;
  generation_question?: string | null;
  citations: CitationView[];
  sources: SourceView[];
  diagnostics?: DiagnosticsView | null;
  created_at: string;
};

export type SessionDetail = SessionSummary & {
  selected_document_ids: string[];
  missing_selected_count: number;
  turns: SessionTurnView[];
};

export type SessionListResponse = {
  sessions: SessionSummary[];
  request_id: string;
};

export type DeleteSessionResponse = {
  session_id: string;
  deleted: boolean;
  already_absent: boolean;
  request_id: string;
};

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    request_id: string;
    turn_id?: string;
    session_id?: string;
  };
};
