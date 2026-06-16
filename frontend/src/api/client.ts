const BASE = "/api";

export function getCsrf(): string | null {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function rawRequest(path: string, options: RequestInit = {}) {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  // Browser must set the multipart boundary itself — never force Content-Type for FormData.
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const method = (options.method ?? "GET").toUpperCase();
  if (UNSAFE.has(method)) {
    const csrf = getCsrf();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  return fetch(`${BASE}${path}`, { ...options, headers, credentials: "same-origin" });
}

// Shared in-flight refresh promise: N concurrent 401s trigger exactly ONE /auth/refresh call.
let refreshing: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  const resp = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
  });
  return resp.ok;
}

export async function tryRefresh(): Promise<boolean> {
  if (refreshing !== null) return refreshing;
  refreshing = doRefresh().finally(() => { refreshing = null; });
  return refreshing;
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

// FastAPI отдаёт detail строкой (HTTPException) или массивом ошибок валидации (422).
function formatDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : JSON.stringify(d)))
      .join("; ");
  }
  return null;
}

export async function api<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  let resp = await rawRequest(path, options);
  if (resp.status === 401 && (await tryRefresh())) {
    resp = await rawRequest(path, options);
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new ApiError(resp.status, formatDetail(body.detail) ?? resp.statusText);
  }
  if (resp.status === 204 || resp.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return resp.json();
}

export async function apiUpload<T = unknown>(path: string, form: FormData): Promise<T> {
  return api<T>(path, { method: "POST", body: form });
}
