import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import AiConfigPage from "./AiConfigPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const EMPTY_USAGE = { total_calls: 0, total_cost_rub: null, by_model: [] };

const SMTP_DEFAULT = { host: "smtp.test", port: "587", user: "u@x.ru", from_addr: "from@x.ru", tls: "true", has_password: false };

// Minimal fetch stub: returns sensible defaults for all API calls the page makes on mount.
function makeFetch(yandexOverride?: Partial<{ client_id: string; has_secret: boolean }>) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const method = (init?.method ?? "GET").toUpperCase();
    if (url.includes("/settings/yandex")) {
      if (method === "PUT") {
        return json({ client_id: "new-id", has_secret: true });
      }
      return json({ client_id: "test-client-id", has_secret: false, ...yandexOverride });
    }
    if (url.includes("/settings/smtp")) {
      if (method === "PUT") {
        return json({ ...SMTP_DEFAULT, has_password: true });
      }
      return json(SMTP_DEFAULT);
    }
    if (url.includes("/settings/dadata")) return json({ has_token: false, has_secret: false });
    if (url.includes("/auth/config")) return json({ yandex_enabled: false });
    if (url.includes("/ai/usage")) return json(EMPTY_USAGE);
    // providers, models, purposes
    return json([]);
  });
}

function renderPage(fetchMock = makeFetch()) {
  vi.stubGlobal("fetch", fetchMock);
  return render(
    <MemoryRouter>
      <AuthProvider>
        <AiConfigPage />
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("AiConfigPage — блок «Яндекс OAuth»", () => {
  it("загружает и показывает client_id из GET /settings/yandex", async () => {
    renderPage();
    expect(await screen.findByDisplayValue("test-client-id")).toBeInTheDocument();
    expect(screen.getByText(/Секрет — не задан/)).toBeInTheDocument();
  });

  it("показывает «задан ✓» когда has_secret=true", async () => {
    renderPage(makeFetch({ client_id: "abc", has_secret: true }));
    expect(await screen.findByText(/задан ✓/)).toBeInTheDocument();
  });

  it("сохранение вызывает PUT /settings/yandex и показывает «Сохранено»", async () => {
    const fetchMock = makeFetch();
    renderPage(fetchMock);
    // Wait for initial load
    await screen.findByDisplayValue("test-client-id");

    // Scope to the Yandex section to disambiguate from the DaData «Сохранить» button
    const yandexSection = screen.getByText("Интеграции · Яндекс OAuth").closest("section")!;
    const secretInput = within(yandexSection).getByLabelText("Secret Яндекс");
    await userEvent.type(secretInput, "my-secret");
    await userEvent.click(within(yandexSection).getByText("Сохранить"));

    expect(await screen.findByText("Сохранено")).toBeInTheDocument();

    const puts = fetchMock.mock.calls.filter(
      (c) => (c[1] as RequestInit)?.method === "PUT" && (c[0] as string).includes("/settings/yandex")
    );
    expect(puts.length).toBe(1);
    expect(JSON.parse((puts[0][1] as RequestInit).body as string)).toMatchObject({ secret: "my-secret" });

    // Secret field cleared after save
    expect(secretInput).toHaveValue("");
  });
});

describe("AiConfigPage — блок «SMTP»", () => {
  it("загружает и показывает SMTP-настройки", async () => {
    renderPage();
    expect(await screen.findByDisplayValue("smtp.test")).toBeInTheDocument();
    expect(screen.getByText(/Пароль — не задан/)).toBeInTheDocument();
  });

  it("показывает «задан ✓» когда has_password=true", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("/settings/smtp")) return json({ ...SMTP_DEFAULT, has_password: true });
      if (url.includes("/settings/yandex")) return json({ client_id: "", has_secret: false });
      if (url.includes("/settings/dadata")) return json({ has_token: false, has_secret: false });
      if (url.includes("/auth/config")) return json({ yandex_enabled: false });
      if (url.includes("/ai/usage")) return json(EMPTY_USAGE);
      return json([]);
    });
    renderPage(fetchMock);
    expect(await screen.findByText(/Пароль — задан ✓/)).toBeInTheDocument();
  });

  it("сохранение вызывает PUT /settings/smtp и показывает «Сохранено»", async () => {
    const fetchMock = makeFetch();
    renderPage(fetchMock);
    await screen.findByDisplayValue("smtp.test");

    const smtpSection = screen.getByText("SMTP (отправка почты)").closest("section")!;
    const passwordInput = within(smtpSection).getByLabelText("SMTP пароль");
    await userEvent.type(passwordInput, "secret123");
    await userEvent.click(within(smtpSection).getByText("Сохранить"));

    await waitFor(() => {
      const puts = fetchMock.mock.calls.filter(
        (c) => (c[1] as RequestInit)?.method === "PUT" && (c[0] as string).includes("/settings/smtp")
      );
      expect(puts.length).toBe(1);
    });
    expect(await screen.findByText("Сохранено")).toBeInTheDocument();
    // Password field cleared after save
    expect(passwordInput).toHaveValue("");
  });
});
