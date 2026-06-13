import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PublicLinksManager from "./PublicLinksManager";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
const LINK = { id: 3, estimate_id: 7, token: "abc123", level: "full", expires_at: null,
  watermark_enabled: false, watermark_text: "", revoked: false, created_at: "2026-06-13T00:00:00Z" };
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("PublicLinksManager", () => {
  it("lists links and shows public url", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([LINK])));
    render(<PublicLinksManager estimateId={7} canEdit={true} />);
    expect(await screen.findByText(/\/p\/abc123/)).toBeInTheDocument();
  });

  it("creates a link (POST) and revokes it (DELETE)", async () => {
    const f = vi.fn(async (_url: string, init?: RequestInit) => {
      const m = init?.method ?? "GET";
      if (m === "POST") return json(LINK, 201);
      if (m === "DELETE") return new Response(null, { status: 204 });
      return json([LINK]);
    });
    vi.stubGlobal("fetch", f);
    render(<PublicLinksManager estimateId={7} canEdit={true} />);
    await userEvent.click(screen.getByText("Создать ссылку"));
    await vi.waitFor(() => expect(f.mock.calls.some((c) => (c[1] as RequestInit | undefined)?.method === "POST")).toBe(true));
    await userEvent.click(await screen.findByText("Отозвать"));
    await vi.waitFor(() => expect(f.mock.calls.some((c) => (c[1] as RequestInit | undefined)?.method === "DELETE")).toBe(true));
  });

  it("hides create/revoke for viewer", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([LINK])));
    render(<PublicLinksManager estimateId={7} canEdit={false} />);
    await screen.findByText(/\/p\/abc123/);
    expect(screen.queryByText("Создать ссылку")).not.toBeInTheDocument();
    expect(screen.queryByText("Отозвать")).not.toBeInTheDocument();
  });
});
