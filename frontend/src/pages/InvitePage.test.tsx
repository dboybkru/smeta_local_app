import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as authModule from "../auth/AuthContext";
import * as orgsApi from "../api/orgs";
import { ApiError } from "../api/client";
import InvitePage from "./InvitePage";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function stubAuth(reloadFn = vi.fn()) {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: null,
    loginWithPassword: vi.fn(),
    reload: reloadFn,
    logout: vi.fn(),
  });
}

function renderInvite(token: string) {
  return render(
    <MemoryRouter initialEntries={[`/invite/${token}`]}>
      <Routes>
        <Route path="/invite/:token" element={<InvitePage />} />
        <Route path="/" element={<div>Home</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("InvitePage", () => {
  it("загружает и показывает информацию о приглашении", async () => {
    stubAuth();
    vi.spyOn(orgsApi, "getInvite").mockResolvedValue({
      email: "alice@test.ru",
      org_name: "Акме",
      role: "estimator",
    });

    renderInvite("valid-token");

    expect(await screen.findByText(/Вас пригласили в/)).toBeInTheDocument();
    expect(screen.getByText("Акме")).toBeInTheDocument();
    expect(screen.getByText("estimator")).toBeInTheDocument();
    expect(screen.getByText("alice@test.ru")).toBeInTheDocument();
  });

  it("успешный accept вызывает reload и переходит на /", async () => {
    const reloadFn = vi.fn().mockResolvedValue(undefined);
    stubAuth(reloadFn);
    vi.spyOn(orgsApi, "getInvite").mockResolvedValue({
      email: "alice@test.ru",
      org_name: "Акме",
      role: "estimator",
    });
    vi.spyOn(orgsApi, "acceptInvite").mockResolvedValue({ status: "active" });

    renderInvite("valid-token");

    await screen.findByText(/Вас пригласили в/);

    await userEvent.type(screen.getByLabelText("Ваше имя"), "Алиса");
    await userEvent.type(screen.getByLabelText("Пароль"), "Pass12345");
    await userEvent.click(screen.getByText("Создать аккаунт и войти"));

    await waitFor(() => {
      expect(orgsApi.acceptInvite).toHaveBeenCalledWith("valid-token", {
        name: "Алиса",
        password: "Pass12345",
      });
    });
    await waitFor(() => {
      expect(reloadFn).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(screen.getByText("Home")).toBeInTheDocument();
    });
  });

  it("показывает «Приглашение не найдено» при 404", async () => {
    stubAuth();
    vi.spyOn(orgsApi, "getInvite").mockRejectedValue(
      new ApiError(404, "Приглашение не найдено")
    );

    renderInvite("bad-token");

    expect(await screen.findByText(/Приглашение не найдено/)).toBeInTheDocument();
  });

  it("показывает «Срок приглашения истёк» при 410", async () => {
    stubAuth();
    vi.spyOn(orgsApi, "getInvite").mockRejectedValue(
      new ApiError(410, "Срок приглашения истёк")
    );

    renderInvite("expired-token");

    expect(await screen.findByText(/Срок приглашения истёк/)).toBeInTheDocument();
  });
});
