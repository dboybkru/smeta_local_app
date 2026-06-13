import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProvidersSection from "./ProvidersSection";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const P = { id: 1, name: "VseGPT", base_url: "https://api.vsegpt.ru/v1", auth_style: "x_api_key", enabled: true, has_key: true };

describe("ProvidersSection", () => {
  it("lists providers with key status", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([P])));
    render(<ProvidersSection version={0} onChanged={() => {}} />);
    expect(await screen.findByText("VseGPT")).toBeInTheDocument();
    expect(screen.getByText("ключ задан")).toBeInTheDocument();
  });

  it("creates a provider (POST) and calls onChanged", async () => {
    const f = vi.fn(async (_url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") return json({ ...P, id: 2, name: "AITunnel" }, 201);
      return json([]);
    });
    vi.stubGlobal("fetch", f);
    const onChanged = vi.fn();
    render(<ProvidersSection version={0} onChanged={onChanged} />);
    await screen.findByText(/Провайдеров пока нет/);
    await userEvent.type(screen.getByPlaceholderText("Название"), "AITunnel");
    await userEvent.type(screen.getByPlaceholderText("https://api.vsegpt.ru/v1"), "https://api.aitunnel.ru/v1/");
    await userEvent.click(screen.getByText("Добавить"));
    expect(onChanged).toHaveBeenCalled();
    const posts = f.mock.calls.filter((c) => ((c[1] as RequestInit)?.method ?? "GET") === "POST");
    expect(posts.length).toBe(1);
  });

  it("imports models and shows count", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if (((init?.method ?? "GET") === "POST") && url.includes("/models/refresh")) return json({ imported: 5 });
      return json([P]);
    });
    vi.stubGlobal("fetch", f);
    render(<ProvidersSection version={0} onChanged={() => {}} />);
    await screen.findByText("VseGPT");
    await userEvent.click(screen.getByText("Импорт моделей"));
    expect(await screen.findByText(/Импортировано моделей: 5/)).toBeInTheDocument();
  });
});
