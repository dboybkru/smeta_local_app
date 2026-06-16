import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import * as authModule from "../auth/AuthContext";
import AdminUsersPage from "./AdminUsersPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const ORG_ID = 7;

function stubOrgAdmin(orgId: number | null = ORG_ID) {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: {
      id: 1,
      email: "admin@org.ru",
      name: "Админ",
      role: "org_admin",
      status: "active",
      is_superuser: false,
      org_id: orgId,
      org_name: orgId != null ? "Акме" : null,
    },
    loginWithPassword: vi.fn(),
    reload: vi.fn(),
    logout: vi.fn(),
  });
}

const USERS = [
  { id: 10, email: "alice@acme.ru", name: "Alice", role: "estimator", status: "active" },
  { id: 11, email: "bob@acme.ru", name: "Bob", role: "viewer", status: "pending" },
];

describe("AdminUsersPage", () => {
  it("renders 'нет организации' state when org_id is null", () => {
    stubOrgAdmin(null);
    vi.stubGlobal("fetch", vi.fn());
    render(<MemoryRouter><AdminUsersPage /></MemoryRouter>);
    expect(screen.getByText(/не привязан к организации/i)).toBeInTheDocument();
  });

  it("loads users from per-org endpoint /api/orgs/{id}/users", async () => {
    stubOrgAdmin();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if ((url as string).includes(`/api/orgs/${ORG_ID}/users`)) return json(USERS);
        return json([]);
      })
    );
    render(<MemoryRouter><AdminUsersPage /></MemoryRouter>);
    expect(await screen.findByText("alice@acme.ru")).toBeInTheDocument();
    expect(screen.getByText("bob@acme.ru")).toBeInTheDocument();
  });

  it("does NOT call the old global /api/admin/users endpoint", async () => {
    stubOrgAdmin();
    const calledUrls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (url: unknown) => {
      calledUrls.push(String(url));
      return json(USERS);
    }));
    render(<MemoryRouter><AdminUsersPage /></MemoryRouter>);
    await screen.findByText("alice@acme.ru");
    expect(calledUrls.some((u) => u.includes("/api/admin/users"))).toBe(false);
    expect(calledUrls.some((u) => u.includes(`/api/orgs/${ORG_ID}/users`))).toBe(true);
  });

  it("shows Одобрить button for pending user and calls PATCH on click", async () => {
    stubOrgAdmin();
    const patchedUrls: string[] = [];
    const fetchMock = vi.fn(async (url: unknown, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PATCH") {
        patchedUrls.push(String(url));
        return json({ ...USERS[1], status: "active" });
      }
      return json(USERS);
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><AdminUsersPage /></MemoryRouter>);
    await screen.findByText("bob@acme.ru");

    await userEvent.click(screen.getByText("Одобрить"));

    await waitFor(() => {
      expect(patchedUrls.length).toBeGreaterThan(0);
      expect(patchedUrls[0]).toContain(`/api/orgs/${ORG_ID}/users/11`);
    });
  });

  it("shows Заблокировать button for active user", async () => {
    stubOrgAdmin();
    vi.stubGlobal("fetch", vi.fn(async () => json(USERS)));
    render(<MemoryRouter><AdminUsersPage /></MemoryRouter>);
    await screen.findByText("alice@acme.ru");
    // Both alice (active) and bob (pending) can be blocked — expect at least one button
    expect(screen.getAllByText("Заблокировать").length).toBeGreaterThanOrEqual(1);
  });
});
