// Central API helpers - mirrors main.py contracts, no backend changes required
export const API_BASE = ""; // same origin

export function getOwnerId(): string {
  return localStorage.getItem("ccl-owner-id") || "";
}
export function setOwnerId(id: string) {
  localStorage.setItem("ccl-owner-id", id);
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  const ownerId = getOwnerId();
  if (ownerId && !headers["X-User-ID"] && !headers["x-user-id"]) {
    headers["X-User-ID"] = ownerId;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  const ct = res.headers.get("content-type") || "";
  const payload = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof payload === "object" && payload !== null ? (payload as any).detail : payload;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return payload as T;
}

export type Project = {
  id: string;
  owner_id: string;
  title: string;
  storage_slug: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
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
