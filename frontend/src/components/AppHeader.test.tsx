import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppHeader from "./AppHeader";
import * as authModule from "../auth/AuthContext";

function stubUser(role: string, extra: Partial<authModule.User> = {}) {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: {
      id: 1,
      email: "a@b.c",
      name: "A",
      role,
      status: "active",
      is_superuser: false,
      org_id: null,
      org_name: null,
      ...extra,
    },
    loginWithPassword: vi.fn(),
    reload: vi.fn(),
    logout: vi.fn(),
  });
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("AppHeader", () => {
  it("shows the catalog link to any user", () => {
    stubUser("estimator");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("Каталог")).toBeInTheDocument();
  });

  it("hides org-admin links from estimator", () => {
    stubUser("estimator");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.queryByText("Импорт")).not.toBeInTheDocument();
    expect(screen.queryByText("Уровни цен")).not.toBeInTheDocument();
    expect(screen.queryByText("Поставщики")).not.toBeInTheDocument();
    expect(screen.queryByText("Пользователи")).not.toBeInTheDocument();
    expect(screen.queryByText("AI")).not.toBeInTheDocument();
    expect(screen.queryByText("Организации")).not.toBeInTheDocument();
  });

  it("shows org-level admin links to org_admin (not superuser)", () => {
    stubUser("org_admin");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("Импорт")).toBeInTheDocument();
    expect(screen.getByText("Уровни цен")).toBeInTheDocument();
    expect(screen.getByText("Поставщики")).toBeInTheDocument();
    expect(screen.getByText("Пользователи")).toBeInTheDocument();
  });

  it("hides AI and Организации from org_admin (not superuser)", () => {
    stubUser("org_admin");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.queryByText("AI")).not.toBeInTheDocument();
    expect(screen.queryByText("Организации")).not.toBeInTheDocument();
  });

  it("shows AI and Организации only to superuser", () => {
    stubUser("org_admin", { is_superuser: true });
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("AI")).toBeInTheDocument();
    expect(screen.getByText("Организации")).toBeInTheDocument();
  });

  it("shows all org-level links to superuser too", () => {
    stubUser("org_admin", { is_superuser: true });
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("Импорт")).toBeInTheDocument();
    expect(screen.getByText("Уровни цен")).toBeInTheDocument();
    expect(screen.getByText("Поставщики")).toBeInTheDocument();
    expect(screen.getByText("Пользователи")).toBeInTheDocument();
  });

  it("hides admin-only links from viewer", () => {
    stubUser("viewer");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.queryByText("Импорт")).not.toBeInTheDocument();
    expect(screen.queryByText("Уровни цен")).not.toBeInTheDocument();
    expect(screen.queryByText("AI")).not.toBeInTheDocument();
    expect(screen.queryByText("Пользователи")).not.toBeInTheDocument();
    expect(screen.queryByText("Организации")).not.toBeInTheDocument();
  });

  it("shows Реквизиты to estimator but hides from viewer", () => {
    stubUser("estimator");
    const { unmount } = render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("Реквизиты")).toBeInTheDocument();
    unmount();
    vi.restoreAllMocks();
    stubUser("viewer");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.queryByText("Реквизиты")).not.toBeInTheDocument();
  });

  it("hides «Организации» link from non-superusers", () => {
    stubUser("org_admin");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.queryByText("Организации")).not.toBeInTheDocument();
  });

  it("shows «Организации» link to superusers", () => {
    stubUser("org_admin", { is_superuser: true });
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("Организации")).toBeInTheDocument();
  });

  it("shows org name in brackets when org_name is set", () => {
    stubUser("estimator", { org_name: "Акме", org_id: 1 });
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("[Акме]")).toBeInTheDocument();
  });

  it("does not show org name when org_name is null", () => {
    stubUser("estimator");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.queryByText(/\[.*\]/)).not.toBeInTheDocument();
  });
});
