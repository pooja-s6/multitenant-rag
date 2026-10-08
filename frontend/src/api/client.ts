export const TOKEN_KEY = "rag.access_token";

export type DependencyCheck = {
  ok: boolean;
  detail: string;
};

export type ReadyResponse = {
  status: "ok" | "degraded";
  checks: Record<string, DependencyCheck>;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type CurrentUser = {
  user_id: string;
  tenant_id: string;
  role: string;
  email: string;
  department: string | null;
};

export type DocumentSummary = {
  id: string;
  filename: string;
  content_type: string;
  chunk_count: number;
  created_at: string;
};

export type Source = {
  document_id: string;
  chunk_id: string;
  filename: string;
  page_number: number | null;
  score: number;
  excerpt: string;
};

export type RagAnswer = {
  answer: string;
  sources: Source[];
  model_used: string;
  cache_hit: boolean;
  latency: number;
  request_id: string;
};

export type ModelCount = {
  model: string;
  total_queries: number;
};

export type DashboardSummary = {
  tenant_id: string;
  total_queries: number;
  cache_hits: number;
  cache_misses: number;
  hit_rate: number;
  average_latency_ms: number;
  p95_latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
  estimated_cost_saved: number;
  model_distribution: ModelCount[];
  queries_by_tenant: { tenant_id: string; total_queries: number }[] | null;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

export function readToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function storeToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

async function send<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (auth) {
    const token = readToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function getReadiness(): Promise<ReadyResponse> {
  const response = await fetch("/api/health/ready");
  const body = (await response.json()) as ReadyResponse;
  if (response.status !== 200 && response.status !== 503) {
    throw new Error("Readiness check failed");
  }
  return body;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  return send<TokenResponse>(
    "/api/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    },
    false,
  );
}

export async function currentUser(): Promise<CurrentUser> {
  return send<CurrentUser>("/api/auth/me");
}

export async function listDocuments(): Promise<DocumentSummary[]> {
  return send<DocumentSummary[]>("/api/documents");
}

export async function uploadDocument(file: File, fields: Record<string, string>): Promise<void> {
  const body = new FormData();
  body.set("file", file);
  for (const [key, value] of Object.entries(fields)) {
    if (value.trim()) {
      body.set(key, value.trim());
    }
  }
  await send("/api/documents", { method: "POST", body });
}

export async function deleteDocument(documentId: string): Promise<void> {
  await send(`/api/documents/${documentId}`, { method: "DELETE" });
}

export async function askQuestion(query: string): Promise<RagAnswer> {
  return send<RagAnswer>("/api/rag/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

export async function dashboardSummary(): Promise<DashboardSummary> {
  return send<DashboardSummary>("/api/dashboard/summary");
}
