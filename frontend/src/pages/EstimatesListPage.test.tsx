import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import * as authModule from "../auth/AuthContext";
import EstimatesListPage from "./EstimatesListPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
function router(map: Record<string, unknown>) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    if ((init?.method ?? "GET") === "POST" && url === "/api/estimates") return json({ id: 99, branches: [] }, 201);
    const k = Object.keys(map).find((x) => url.startsWith(x));
    return json(k ? map[k] : { detail: "x" }, k ? 200 : 404);
  });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function stubUser(role = "estimator") {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role, status: "active", is_superuser: false, org_id: null, org_name: null },
    loginWithPassword: vi.fn(), reload: vi.fn(), logout: vi.fn(),
  });
}

function renderPage() {
  return render(<MemoryRouter><AuthProvider><EstimatesListPage /></AuthProvider></MemoryRouter>);
}

const LIST = [{ id: 1, client_id: null, owner_id: 1, object_name: "Склад", status: "draft", vat_enabled: false, vat_rate: "20.00", branches: [] }];

describe("EstimatesListPage", () => {
  it("lists estimates", async () => {
    vi.stubGlobal("fetch", router({ "/api/estimates": LIST, "/api/clients": [] }));
    stubUser();
    renderPage();
    expect(await screen.findByText("Склад")).toBeInTheDocument();
  });

  it("creates an estimate (POST fires)", async () => {
    const f = router({ "/api/estimates": LIST, "/api/clients": [] });
    vi.stubGlobal("fetch", f);
    stubUser();
    renderPage();
    await screen.findByText("Склад");
    await userEvent.type(screen.getByPlaceholderText("Название объекта"), "Новый объект");
    await userEvent.click(screen.getByText("Создать смету"));
    await screen.findByText("Склад");
    const posted = f.mock.calls.some(
      (c) => c[0] === "/api/estimates" && (c[1] as RequestInit | undefined)?.method === "POST",
    );
    expect(posted).toBe(true);
  });
});
