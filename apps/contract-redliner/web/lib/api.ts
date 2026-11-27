import type {
  DocumentOut,
  FindingOut,
  PlaybookOut,
  ReviewDetail,
  ReviewOut,
  RuleOut,
  SearchResponse,
  TokenResponse,
  UserOut,
} from "./types";

const TOKEN_KEY = "clauseguard.token";
const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  auth = true,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    const message =
      typeof detail === "object" && detail && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `Request failed (${response.status})`;
    throw new ApiError(message, response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) return (await response.json()) as T;
  return (await response.text()) as unknown as T;
}

export const api = {
  async register(input: {
    tenant_name: string;
    email: string;
    password: string;
    full_name?: string;
  }): Promise<TokenResponse> {
    const result = await request<TokenResponse>("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(input),
    }, false);
    setToken(result.access_token);
    return result;
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const body = new URLSearchParams({ username: email, password });
    const result = await request<TokenResponse>("/v1/auth/token", {
      method: "POST",
      body,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    }, false);
    setToken(result.access_token);
    return result;
  },

  logout(): void {
    setToken(null);
  },

  async me(): Promise<UserOut> {
    return request<UserOut>("/v1/auth/me");
  },

  async documents(): Promise<DocumentOut[]> {
    return request<DocumentOut[]>("/v1/documents");
  },

  async upload(file: File): Promise<DocumentOut> {
    const body = new FormData();
    body.append("file", file);
    return request<DocumentOut>("/v1/documents", { method: "POST", body });
  },

  async playbooks(): Promise<PlaybookOut[]> {
    return request<PlaybookOut[]>("/v1/playbooks");
  },

  async createPlaybook(input: {
    name: string;
    description: string;
    rules: RuleOut[];
  }): Promise<PlaybookOut> {
    return request<PlaybookOut>("/v1/playbooks", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async reviews(): Promise<ReviewOut[]> {
    return request<ReviewOut[]>("/v1/reviews");
  },

  async startReview(documentId: string, playbookId: string, reviewerRole = "customer"): Promise<ReviewOut> {
    return request<ReviewOut>(`/v1/documents/${documentId}/reviews`, {
      method: "POST",
      body: JSON.stringify({ playbook_id: playbookId, reviewer_role: reviewerRole }),
    });
  },

  async review(id: string): Promise<ReviewDetail> {
    return request<ReviewDetail>(`/v1/reviews/${id}`);
  },

  async patchFinding(
    id: string,
    patch: { status?: FindingOut["status"]; reviewer_note?: string },
  ): Promise<FindingOut> {
    return request<FindingOut>(`/v1/findings/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
  },

  async search(query: string, limit = 10): Promise<SearchResponse> {
    return request<SearchResponse>("/v1/search", {
      method: "POST",
      body: JSON.stringify({ query, limit }),
    });
  },

  async exportUrl(reviewId: string, format: "docx" | "pdf" | "md" | "json"): Promise<void> {
    const token = getToken();
    const response = await fetch(`${API_URL}/v1/reviews/${reviewId}/export`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ format, include_dismissed: false }),
    });
    if (!response.ok) throw new ApiError(`Export failed (${response.status})`, response.status);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `clauseguard-${reviewId}.${format}`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  },
};