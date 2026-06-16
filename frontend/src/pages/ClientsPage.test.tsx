import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import * as authModule from "../auth/AuthContext";
import ClientsPage from "./ClientsPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function stub() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role: "admin", status: "active", is_superuser: false, org_id: null, org_name: null },
    loginWithPassword: vi.fn(), acceptTokens: vi.fn(), logout: vi.fn(),
  });
}
const CLIENT = { id: 1, name: "ООО Ромашка", default_price_level_id: null, inn: "7707083893",
  kpp: null, ogrn: null, type: null, address: "Москва", actual_address: null, phone: null,
  email: null, contact_person: null, bank_name: null, bank_account: null, bik: null };

describe("ClientsPage", () => {
  it("lists clients", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([CLIENT])));
    stub();
    render(<MemoryRouter><AuthProvider><ClientsPage /></AuthProvider></MemoryRouter>);
    expect(await screen.findByText("ООО Ромашка")).toBeInTheDocument();
  });

  it("creates a client via DaData autofill", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/clients/suggest")) return json([{ value: "ПАО Сбербанк", inn: "7707083893",
        kpp: "773601001", ogrn: "1", name_short: "ПАО Сбербанк", address: "Москва",
        management: "Греф", type: "LEGAL", status: "ACTIVE" }]);
      if ((init?.method ?? "GET") === "POST" && url.endsWith("/clients"))
        return json({ ...CLIENT, id: 2, name: "ПАО Сбербанк" }, 201);
      return json([]);
    });
    vi.stubGlobal("fetch", f);
    stub();
    render(<MemoryRouter><AuthProvider><ClientsPage /></AuthProvider></MemoryRouter>);
    await userEvent.click(await screen.findByText("Добавить клиента"));
    await userEvent.type(screen.getByLabelText("Поиск в DaData"), "сбер");
    await userEvent.click(await screen.findByText(/ПАО Сбербанк/));
    expect((screen.getByLabelText("ИНН") as HTMLInputElement).value).toBe("7707083893");
    await userEvent.click(screen.getByText("Сохранить"));
    const posts = f.mock.calls.filter((c) => ((c[1] as RequestInit)?.method ?? "GET") === "POST");
    expect(posts.length).toBe(1);
  });
});
