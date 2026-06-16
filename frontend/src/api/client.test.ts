import { afterEach, describe, expect, it, vi } from "vitest";
import { getCsrf, tryRefresh, api } from "./client";

function jsonResp(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  // Clear any csrf cookie set during tests
  document.cookie = "csrf_token=; max-age=0; path=/";
});

// Helper to set a cookie in jsdom
function setCsrfCookie(value: string) {
  document.cookie = `csrf_token=${value}; path=/`;
}

describe("getCsrf", () => {
  it("returns null when no csrf_token cookie", () => {
    expect(getCsrf()).toBeNull();
  });

  it("returns csrf value when cookie is present", () => {
    setCsrfCookie("test-csrf-123");
    expect(getCsrf()).toBe("test-csrf-123");
  });
});

describe("X-CSRF-Token header", () => {
  it("sends X-CSRF-Token header on POST when csrf cookie is present", async () => {
    setCsrfCookie("my-csrf-token");
    const fetchMock = vi.fn(async () => jsonResp({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await api("/some/resource", { method: "POST", body: JSON.stringify({}) });
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("my-csrf-token");
  });

  it("does NOT send X-CSRF-Token on GET", async () => {
    setCsrfCookie("my-csrf-token");
    const fetchMock = vi.fn(async () => jsonResp({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await api("/some/resource", { method: "GET" });
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
  });

  it("does NOT send X-CSRF-Token on POST when no csrf cookie", async () => {
    const fetchMock = vi.fn(async () => jsonResp({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await api("/some/resource", { method: "POST", body: JSON.stringify({}) });
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
  });

  it("sends credentials: same-origin on every request", async () => {
    const fetchMock = vi.fn(async () => jsonResp({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await api("/some/resource");
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.credentials).toBe("same-origin");
  });
});

describe("tryRefresh", () => {
  it("returns true when refresh endpoint returns ok", async () => {
    const fetchMock = vi.fn(async () => jsonResp({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    const result = await tryRefresh();
    expect(result).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain("/auth/refresh");
    expect(init.credentials).toBe("same-origin");
  });

  it("returns false when refresh endpoint returns non-ok", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResp({ detail: "Unauthorized" }, 401)));
    const result = await tryRefresh();
    expect(result).toBe(false);
  });

  it("two concurrent 401 flows cause exactly ONE /auth/refresh fetch call", async () => {
    let refreshCallCount = 0;
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes("/auth/refresh")) {
        refreshCallCount++;
        // Simulate network latency so both callers overlap
        await new Promise((r) => setTimeout(r, 10));
        return jsonResp({ ok: true });
      }
      // Return 401 on first call to trigger refresh, 200 on subsequent
      if (refreshCallCount === 0) {
        return new Response(JSON.stringify({ detail: "Unauthorized" }), { status: 401 });
      }
      return jsonResp({ ok: true });
    });
    vi.stubGlobal("fetch", fetchMock);

    // Fire two concurrent api() calls that will both hit 401 and race to refresh
    const [r1, r2] = await Promise.all([
      api("/some/resource"),
      api("/some/resource"),
    ]);

    expect(r1).toEqual({ ok: true });
    expect(r2).toEqual({ ok: true });
    expect(refreshCallCount).toBe(1);
  });
});
