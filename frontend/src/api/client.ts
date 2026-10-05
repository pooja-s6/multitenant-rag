export type DependencyCheck = {
  ok: boolean;
  detail: string;
};

export type ReadyResponse = {
  status: "ok" | "degraded";
  checks: Record<string, DependencyCheck>;
};

export type ApiError = {
  status: number;
  detail: string;
};

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

export async function getReadiness(): Promise<ReadyResponse> {
  const response = await fetch("/api/health/ready");
  const body = (await response.json()) as ReadyResponse;
  if (response.status !== 200 && response.status !== 503) {
    throw new Error("Readiness check failed");
  }
  return body;
}

export async function login(email: string, password: string): Promise<ApiError> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return { status: response.status, detail: await readDetail(response) };
}
