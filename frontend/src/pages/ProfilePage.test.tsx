import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import * as authModule from "../auth/AuthContext";
import ProfilePage from "./ProfilePage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
const EMPTY = { id: 0, org_name: "", inn: "", contacts: { phone: "", email: "", address: "", site: "" },
  bank_requisites: "", utp: [], cases: [], guarantee: "", logo_url: "", updated_at: "1970-01-01T00:00:00Z" };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function stub() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role: "estimator", status: "active", is_superuser: false, org_id: null, org_name: null },
    loginWithPassword: vi.fn(), reload: vi.fn(), logout: vi.fn(),
  });
}
function renderPage() {
  return render(<MemoryRouter><AuthProvider><ProfilePage /></AuthProvider></MemoryRouter>);
}

describe("ProfilePage", () => {
  it("loads empty profile then saves via PUT", async () => {
    const f = vi.fn(async (_url: string, init?: RequestInit) =>
      (init?.method ?? "GET") === "PUT" ? json({ ...EMPTY, org_name: "ООО Ромашка" }) : json(EMPTY));
    vi.stubGlobal("fetch", f); stub(); renderPage();
    const org = await screen.findByLabelText("Организация");
    await userEvent.type(org, "ООО Ромашка");
    await userEvent.click(screen.getByText("Сохранить"));
    const put = f.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "PUT");
    expect(put).toBeTruthy();
    expect((put![1] as RequestInit).body).toContain("ООО Ромашка");
  });

  it("adds and removes a УТП item", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(EMPTY))); stub(); renderPage();
    await screen.findByLabelText("Организация");
    await userEvent.type(screen.getByPlaceholderText("Новое УТП"), "Гарантия 5 лет");
    await userEvent.click(screen.getByText("+ УТП"));
    expect(screen.getByText("Гарантия 5 лет")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Удалить УТП Гарантия 5 лет"));
    expect(screen.queryByText("Гарантия 5 лет")).not.toBeInTheDocument();
  });
});
