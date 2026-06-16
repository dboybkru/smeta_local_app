import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import * as authModule from "../auth/AuthContext";
import SuppliersPage from "./SuppliersPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function stubAdmin() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role: "admin", status: "active", is_superuser: false, org_id: null, org_name: null },
    loginWithPassword: vi.fn(), acceptTokens: vi.fn(), logout: vi.fn(),
  });
}
function renderPage() {
  return render(<MemoryRouter><AuthProvider><SuppliersPage /></AuthProvider></MemoryRouter>);
}
const SUP = { id: 1, name: "Optimus", column_mapping_template: null };

describe("SuppliersPage", () => {
  it("lists suppliers", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([SUP])));
    stubAdmin(); renderPage();
    expect(await screen.findByText("Optimus")).toBeInTheDocument();
  });

  it("shows empty hint when none", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([])));
    stubAdmin(); renderPage();
    expect(await screen.findByText(/Поставщиков пока нет/)).toBeInTheDocument();
  });

  it("creates a supplier (POST) and shows it", async () => {
    const f = vi.fn(async (_url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") return json({ id: 2, name: "Bolid", column_mapping_template: null }, 201);
      return json([]);
    });
    vi.stubGlobal("fetch", f);
    stubAdmin(); renderPage();
    await screen.findByText(/Поставщиков пока нет/);
    await userEvent.type(screen.getByPlaceholderText("Название"), "Bolid");
    await userEvent.click(screen.getByText("Добавить"));
    expect(await screen.findByText("Bolid")).toBeInTheDocument();
  });

  it("shows 409 message on duplicate name", async () => {
    const f = vi.fn(async (_url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") return json({ detail: "Поставщик существует" }, 409);
      return json([]);
    });
    vi.stubGlobal("fetch", f);
    stubAdmin(); renderPage();
    await screen.findByText(/Поставщиков пока нет/);
    await userEvent.type(screen.getByPlaceholderText("Название"), "Optimus");
    await userEvent.click(screen.getByText("Добавить"));
    expect(await screen.findByText(/уже существует/)).toBeInTheDocument();
  });
});
