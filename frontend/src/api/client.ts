const BASE = "/api";

export function getTokens() {
  return {
    access: localStorage.getItem("access_token"),
    refresh: localStorage.getItem("refresh_token"),
  };
}

// TODO(security): перед публичным запуском рассмотреть httpOnly-cookie вместо localStorage
export function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

async function rawRequest(path: string, options: RequestInit = {}) {
  const { access } = getTokens();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (access) headers["Authorization"] = `Bearer ${access}`;
  return fetch(`${BASE}${path}`, { ...options, headers });
}

// TODO(v2): общий refresh-promise, чтобы параллельные 401 не гонялись за refresh
async function tryRefresh(): Promise<boolean> {
  const { refresh } = getTokens();
  if (!refresh) return false;
  const resp = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!resp.ok) return false;
  const body = await resp.json().catch(() => null);
  if (!body?.access_token || !body?.refresh_token) return false;
  setTokens(body.access_token, body.refresh_token);
  return true;
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
  return resp.json();
}
