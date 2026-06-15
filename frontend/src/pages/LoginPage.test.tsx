import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import LoginPage from "./LoginPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("LoginPage", () => {
  it("показывает форму входа без кнопки Яндекса когда yandex_enabled=false", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ yandex_enabled: false })));
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Пароль")).toBeInTheDocument();
    // Яндекс-кнопка не должна появиться
    await waitFor(() => {
      expect(screen.queryByText("Войти с Яндексом")).not.toBeInTheDocument();
    });
  });

  it("показывает кнопку Яндекса когда yandex_enabled=true", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ yandex_enabled: true })));
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );
    expect(await screen.findByText("Войти с Яндексом")).toBeInTheDocument();
  });

  it("скрывает кнопку Яндекса если запрос конфига упал", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("network error"); }));
    render(
      <MemoryRouter>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("Войти с Яндексом")).not.toBeInTheDocument();
    });
  });
});
