// Same-origin API client. Session cookies are HttpOnly and never held in JavaScript.
export const API_BASE = ""; // same origin
export const WORKFLOW_TRACE_LIMIT = 50;

let currentUserId = "";
export function getOwnerId(): string {
  return currentUserId;
}
export function setOwnerId(id: string) {
  currentUserId = id;
}

function csrfToken(): string {
  const cookie = document.cookie.split("; ").find((item) => item.startsWith("ccl_csrf="));
  return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  const method = (options.method || "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken()) {
    headers["X-CSRF-Token"] = csrfToken();
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  const ct = res.headers.get("content-type") || "";
  const payload = res.status === 204 || res.status === 205
    ? null
    : ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof payload === "object" && payload !== null ? (payload as any).detail : payload;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return payload as T;
}

export type AuthUser = { id: string; email: string; role: string };
export type InvitationResult = {
  id: string;
  email: string;
  role: string;
  expires_at: string;
  invite_url: string;
};

export type Project = {
  id: string;
  owner_id: string;
  title: string;
  storage_slug: string;
  description: string;
  category: string;
  scope: string;
  deadline: string | null;
  outputs: string[];
  responsible_person: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Workflow = {
  id: string;
  project_id: string;
  created_by_id: string | null;
  name: string;
  status: string;
  state: "ready" | "in_progress" | "review" | "changes_required" | "approved" | "archived";
  version: number;
  created_at: string;
  updated_at: string;
};

export type ApprovalStatus = "pending" | "approved" | "rejected" | "cancelled";
export type ApprovalDecision = Exclude<ApprovalStatus, "pending">;

export type Approval = {
  id: string;
  workflow_id: string;
  action_id: string | null;
  requested_by_id: string | null;
  approved_by_id: string | null;
  status: ApprovalStatus;
  decision_code: string | null;
  requested_at: string;
  decided_at: string | null;
};

export type WorkflowToolName = "files.summary" | "knowledge.search" | "research.summary";

export type WorkflowToolRun = {
  id: string;
  project_id: string;
  workflow_id: string;
  requested_by_id: string | null;
  trace_id: string;
  tool_name: WorkflowToolName;
  status: "succeeded" | "failed" | "blocked";
  attempt_count: number;
  max_attempts: number;
  input_summary: string;
  output_summary: string;
  error_code: string | null;
  result: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
};

export type WorkflowAction = {
  id: string;
  project_id: string;
  workflow_id: string;
  requested_by_id: string | null;
  executed_by_id: string | null;
  action_code: "send" | "delete" | "replace" | "publish" | "archive" | "approve";
  target_ref: string;
  reason: string;
  idempotency_key: string | null;
  status: "pending_approval" | "approved" | "rejected" | "cancelled" | "executed";
  approval_id: string | null;
  result_summary: string | null;
  created_at: string;
  approved_at: string | null;
  executed_at: string | null;
};

export type AgentName = "intake" | "research" | "knowledge" | "quality_control";
export type AgentActorName = "orchestrator" | AgentName;
export type AgentHandoffStatus = "completed" | "blocked" | "failed";

export type AgentDefinition = {
  agent: AgentName;
  label: string;
  responsibility: string;
  allowed_tools: string[];
  handoff_targets: AgentName[];
};

export type AgentHandoff = {
  id: string;
  project_id: string;
  workflow_id: string;
  requested_by_id: string | null;
  trace_id: string;
  source_agent: AgentActorName;
  target_agent: AgentName;
  status: AgentHandoffStatus;
  input_summary: string;
  output_summary: string;
  blocked_reason: string | null;
  result: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
};

export type FileRecord = {
  id: string;
  project_id: string;
  storage_key: string;
  name: string;
  extension: string;
  media_type: string;
  size_bytes: number;
  checksum_sha256: string;
  modified_at: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type KnowledgeSource = {
  id: string;
  project_id: string;
  file_id: string;
  owner_id: string;
  title: string;
  source_type: "sop" | "prompt_bank" | "style_guide" | "project_rule";
  sensitivity: "public" | "internal" | "confidential" | "restricted";
  approval_status: "pending" | "approved" | "rejected";
  file_name: string;
  file_storage_key: string;
  file_checksum_sha256: string;
  created_at: string;
  reviewed_at?: string | null;
  rejection_reason?: string | null;
};

export type Backup = {
  id: string;
  project_id: string;
  artifact_key: string;
  manifest_key: string;
  archive_size_bytes: number;
  file_count: number;
  total_bytes: number;
  archive_checksum_sha256: string;
  manifest_checksum_sha256: string;
  status: string;
  created_at: string;
};

export type SearchResult = {
  chunk_id: string;
  score: number;
  title: string;
  heading?: string | null;
  location: string;
  content: string;
  source_type: string;
  sensitivity: string;
  file_name: string;
  line_start: number;
  line_end: number;
};

export type AnswerCitation = {
  citation_number: number;
  chunk_id: string;
  source_id: string;
  score: number;
  title: string;
  heading?: string | null;
  location: string;
  line_start: number;
  line_end: number;
  file_name: string;
  file_storage_key: string;
  excerpt: string;
};

export type KnowledgeAnswerResponse = {
  contract_version: "grounded-answer-v1";
  instruction_version: "knowledge-agent-v1";
  answer_mode: "extractive";
  project_id: string;
  query: string;
  status: "answered" | "refused";
  answer: string;
  refusal_reason: "unsupported_query" | "insufficient_evidence" | null;
  answer_engine: string;
  embedding_model: string;
  embedding_dimensions: number;
  retrieved_count: number;
  citation_count: number;
  citations: AnswerCitation[];
};

export type ResearchClaimClassification =
  | "factual"
  | "heading"
  | "instruction"
  | "opinion"
  | "creative";

export type ResearchScope = {
  model_year: number | null;
  engine: string | null;
  market: string | null;
  population: string | null;
  setting: string | null;
  evidence_type: string | null;
};

export type ResearchClaim = {
  claim_id: string;
  claim: string;
  classification: ResearchClaimClassification;
  source_title: string;
  source_reference: string;
  source_date: string | null;
  passage: string;
  scope: ResearchScope;
  review_status: "needs_review";
};

export type ResearchClaimExtractionResponse = {
  schema_version: "research-evidence-v1";
  project_id: string;
  source_title: string;
  source_reference: string;
  source_date: string | null;
  scope: ResearchScope;
  claim_count: number;
  claims: ResearchClaim[];
};

export type ResearchApplicabilityField = {
  field: keyof ResearchScope;
  status: "match" | "mismatch" | "uncertain" | "not_requested";
  requested: string | null;
  observed: string | null;
};

export type ResearchApplicabilityResponse = {
  schema_version: "research-evidence-v1";
  project_id: string;
  claim_id: string;
  claim_classification: ResearchClaimClassification;
  status: "applicable" | "mismatch" | "uncertain" | "not_applicable";
  reason: string;
  fields: ResearchApplicabilityField[];
};

export type ResearchEvidenceWarningCode =
  | "missing_evidence"
  | "source_mismatch"
  | "duplicate_claim"
  | "conflict"
  | "unsupported_claim";

export type ResearchEvidenceWarning = {
  code: ResearchEvidenceWarningCode;
  severity: "error" | "warning";
  claim_id: string;
  message: string;
  related_claim_ids: string[];
};

export type ResearchEvidenceAssessment = {
  claim_id: string;
  status: "supported" | "needs_review" | "not_applicable";
  warning_codes: ResearchEvidenceWarningCode[];
};

export type ResearchEvidenceRegisterResponse = {
  schema_version: "research-evidence-v1";
  project_id: string;
  status: "clear" | "warnings";
  claim_count: number;
  warning_count: number;
  supported_count: number;
  needs_review_count: number;
  not_applicable_count: number;
  assessments: ResearchEvidenceAssessment[];
  warnings: ResearchEvidenceWarning[];
};

export type ResearchReviewStatus =
  | "needs_review"
  | "changes_requested"
  | "verified"
  | "approved";

export type ResearchReviewClaimStatus = "needs_review" | "changes_requested" | "verified";

export type ResearchReviewClaim = {
  claim_id: string;
  review_status: ResearchReviewClaimStatus;
  classification: ResearchClaimClassification;
  claim: string;
  original_claim: string;
  corrected_claim: string | null;
  source_title: string;
  source_reference: string;
  source_date: string | null;
  passage: string;
  scope: ResearchScope;
  original_scope: ResearchScope;
  corrected_scope: ResearchScope | null;
  correction_note: string | null;
  verified_by_id: string | null;
  verified_at: string | null;
};

export type ResearchReviewEvent = {
  id: string;
  claim_id: string | null;
  actor_id: string | null;
  action: "submitted" | "correction_requested" | "verified" | "approved" | "exported";
  note: string | null;
  created_at: string;
};

export type ResearchReviewResponse = {
  schema_version: "research-review-v1";
  id: string;
  project_id: string;
  status: ResearchReviewStatus;
  source_title: string;
  source_reference: string;
  source_date: string | null;
  target_scope: ResearchScope;
  created_by_id: string | null;
  approved_by_id: string | null;
  approved_at: string | null;
  claim_count: number;
  verified_count: number;
  warning_count: number;
  claims: ResearchReviewClaim[];
  warnings: ResearchEvidenceWarning[];
  events: ResearchReviewEvent[];
};

export type KnowledgeFeedbackRating = "helpful" | "not_helpful";
export type KnowledgeFeedbackReason =
  | "accurate"
  | "clear"
  | "missing_evidence"
  | "wrong_source"
  | "other";

export type KnowledgeErrorCategory =
  | "wrong_answer"
  | "missing_evidence"
  | "wrong_source"
  | "technical_error"
  | "other";
