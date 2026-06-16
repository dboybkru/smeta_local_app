import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import * as authModule from "../auth/AuthContext";
import OrgsPage from "./OrgsPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubSuperuser() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: {
      id: 1,
      email: "super@test.ru",
      name: "Супер",
      role: "org_admin",
      status: "active",
      is_superuser: true,
      org_id: null,
      org_name: null,
    },
    loginWithPassword: vi.fn(),
    acceptTokens: vi.fn(),
    logout: vi.fn(),
  });
}

function stubNonSuperuser() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: {
      id: 2,
      email: "user@test.ru",
      name: "Юзер",
      role: "estimator",
      status: "active",
      is_superuser: false,
      org_id: 1,
      org_name: "Акме",
    },
    loginWithPassword: vi.fn(),
    acceptTokens: vi.fn(),
    logout: vi.fn(),
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("OrgsPage", () => {
  it("показывает заглушку «Доступ запрещён» для не-суперюзера", () => {
    stubNonSuperuser();
    vi.stubGlobal("fetch", vi.fn());
    render(
      <MemoryRouter>
        <OrgsPage />
      </MemoryRouter>
    );
    expect(screen.getByText("Доступ запрещён.")).toBeInTheDocument();
  });

  it("рендерит заголовок «Организации» для суперюзера", async () => {
    stubSuperuser();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if ((url as string).includes("/api/orgs")) return json([]);
        return json([]);
      })
    );
    render(
      <MemoryRouter>
        <OrgsPage />
      </MemoryRouter>
    );
    // "Организации" appears both as the <h1> heading and as the nav link for superusers
    expect(screen.getAllByText("Организации").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("heading", { name: "Организации" })).toBeInTheDocument();
  });

  it("показывает список организаций", async () => {
    stubSuperuser();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json([{ id: 1, name: "Акме", user_count: 5 }]))
    );
    render(
      <MemoryRouter>
        <OrgsPage />
      </MemoryRouter>
    );
    expect(await screen.findByText("Акме")).toBeInTheDocument();
    expect(screen.getByText("5 польз.")).toBeInTheDocument();
  });

  it("можно создать новую организацию", async () => {
    stubSuperuser();
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") {
        return json({ id: 2, name: "Новая", user_count: 0 });
      }
      return json([{ id: 1, name: "Акме", user_count: 3 }]);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <OrgsPage />
      </MemoryRouter>
    );

    const input = screen.getByLabelText("Название новой организации");
    await userEvent.type(input, "Новая");
    await userEvent.click(screen.getByText("Создать"));

    await waitFor(() => {
      const postCalls = fetchMock.mock.calls.filter(
        (c) => ((c[1] as RequestInit)?.method ?? "GET") === "POST"
      );
      expect(postCalls.length).toBeGreaterThan(0);
    });
  });
});
