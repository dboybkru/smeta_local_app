import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppHeader from "./AppHeader";
import * as authModule from "../auth/AuthContext";

function stubUser(role: string) {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role, status: "active" },
    loginWithPassword: vi.fn(),
    acceptTokens: vi.fn(),
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

  it("hides admin-only links from non-admins", () => {
    stubUser("estimator");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.queryByText("Импорт")).not.toBeInTheDocument();
    expect(screen.queryByText("Уровни цен")).not.toBeInTheDocument();
    expect(screen.queryByText("AI")).not.toBeInTheDocument();
  });

  it("shows admin-only links to admins", () => {
    stubUser("admin");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("Импорт")).toBeInTheDocument();
    expect(screen.getByText("Уровни цен")).toBeInTheDocument();
    expect(screen.getByText("Пользователи")).toBeInTheDocument();
    expect(screen.getByText("AI")).toBeInTheDocument();
  });

  it("shows Реквизиты to estimator/admin but hides from viewer", () => {
    stubUser("estimator");
    const { unmount } = render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("Реквизиты")).toBeInTheDocument();
    unmount();
    vi.restoreAllMocks();
    stubUser("viewer");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.queryByText("Реквизиты")).not.toBeInTheDocument();
  });
});
