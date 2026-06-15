import { afterEach, describe, expect, it, vi } from "vitest";
import { clearTokens, setTokens, tryRefresh, api } from "./client";

function jsonResp(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  clearTokens();
  // Reset the module-level refreshing promise between tests by re-importing would
  // require dynamic imports; instead we just ensure each test sets up fetch fresh.
  localStorage.clear();
});

describe("tryRefresh", () => {
  it("returns false when no refresh token is stored", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const result = await tryRefresh();
    expect(result).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns true and sets tokens on success", async () => {
    setTokens("old-access", "old-refresh");
    vi.stubGlobal("fetch", vi.fn(async () =>
      jsonResp({ access_token: "new-access", refresh_token: "new-refresh" })
    ));
    const result = await tryRefresh();
    expect(result).toBe(true);
    expect(localStorage.getItem("access_token")).toBe("new-access");
    expect(localStorage.getItem("refresh_token")).toBe("new-refresh");
  });

  it("clears tokens and returns false on failed refresh", async () => {
    setTokens("old-access", "old-refresh");
    vi.stubGlobal("fetch", vi.fn(async () => jsonResp({ detail: "Unauthorized" }, 401)));
    const result = await tryRefresh();
    expect(result).toBe(false);
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("two concurrent 401 flows cause exactly ONE /auth/refresh fetch call", async () => {
    setTokens("old-access", "old-refresh");

    let refreshCallCount = 0;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes("/auth/refresh")) {
        refreshCallCount++;
        // Simulate network latency so both callers overlap
        await new Promise((r) => setTimeout(r, 10));
        return jsonResp({ access_token: "new-access", refresh_token: "new-refresh" });
      }
      if ((init?.method ?? "GET") === "GET") {
        // First call → 401, second call (after refresh) → 200
        const access = localStorage.getItem("access_token");
        if (access === "old-access") {
          return new Response(JSON.stringify({ detail: "Unauthorized" }), { status: 401 });
        }
        return jsonResp({ ok: true });
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
