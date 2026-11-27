export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type ReviewStatus = "queued" | "extracting" | "reviewing" | "completed" | "failed";
export type FindingStatus = "open" | "accepted" | "rejected" | "dismissed";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  tenant_id: string;
  role: string;
}

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: string;
  tenant_id: string;
}

export interface DocumentOut {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  page_count: number;
  status: string;
  error: string | null;
  created_at: string;
}

export interface FindingOut {
  id: string;
  rule_id: string;
  title: string;
  severity: Severity;
  status: FindingStatus;
  quote: string;
  page: number;
  suggested_text: string;
  rationale: string;
  market_standard: string;
  confidence: number;
  clause_id: string;
  reviewer_note: string;
}

export interface ReviewOut {
  id: string;
  document_id: string;
  playbook_id: string;
  reviewer_role: string;
  status: ReviewStatus;
  progress: number;
  model: string;
  error: string | null;
  created_at: string;
  finding_count: number;
}

export interface ReviewDetail extends ReviewOut {
  document: DocumentOut;
  findings: FindingOut[];
}

export interface RuleOut {
  id: string;
  title: string;
  category: string;
  severity: Severity;
  description?: string;
  patterns?: string[];
  must_include?: string[];
  market_standard?: string;
  guidance?: string;
  suggested_text?: string;
  redline_strategy?: "replace" | "insert_after" | "delete" | "flag";
  applies_to?: string[];
  weight?: number;
}

export interface PlaybookOut {
  id: string;
  name: string;
  version: number;
  description: string;
  is_active: boolean;
  created_at: string;
  rule_count: number;
}

export interface SearchHit {
  id: string;
  title: string;
  source: string;
  score: number;
  snippet: string;
}

export interface SearchResponse {
  query: string;
  hits: SearchHit[];
  took_ms: number;
}

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEVERITY_STYLES: Record<Severity, string> = {
  critical: "bg-red-100 text-red-800 ring-red-200",
  high: "bg-orange-100 text-orange-800 ring-orange-200",
  medium: "bg-amber-100 text-amber-800 ring-amber-200",
  low: "bg-sky-100 text-sky-800 ring-sky-200",
  info: "bg-slate-100 text-slate-700 ring-slate-200",
};