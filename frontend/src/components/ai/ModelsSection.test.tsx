import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ModelsSection from "./ModelsSection";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const PROV = { id: 1, name: "VseGPT", base_url: "u", auth_style: "x_api_key", enabled: true, has_key: true };
const M = { id: 10, provider_id: 1, model_id: "gpt-4o", label: "GPT-4o", input_price: null, output_price: null, strengths: "", enabled: true };

function route(url: string) {
  if (url.includes("/ai/providers")) return json([PROV]);
  if (url.includes("/ai/models")) return json([M]);
  return json([]);
}

describe("ModelsSection", () => {
  it("hides rows until a search query is entered, then shows match", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => route(url)));
    render(<ModelsSection version={0} onChanged={() => {}} />);
    // before searching: hint shown, no model row
    expect(await screen.findByText(/Введите название модели/)).toBeInTheDocument();
    expect(screen.queryByText("gpt-4o")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Поиск модели"), "gpt");
    expect(await screen.findByText("gpt-4o")).toBeInTheDocument();
  });

  it("shows 'not found' for a non-matching query", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => route(url)));
    render(<ModelsSection version={0} onChanged={() => {}} />);
    await screen.findByText(/Введите название модели/);
    await userEvent.type(screen.getByLabelText("Поиск модели"), "zzz");
    expect(await screen.findByText(/Ничего не найдено/)).toBeInTheDocument();
  });

  it("saves input price on blur (PUT)", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PUT") return json({ ...M, input_price: "10" });
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<ModelsSection version={0} onChanged={() => {}} />);
    await userEvent.type(await screen.findByLabelText("Поиск модели"), "gpt");
    const input = await screen.findByLabelText("Вход gpt-4o");
    await userEvent.type(input, "10");
    await userEvent.tab();
    const puts = f.mock.calls.filter((c) => (c[1] as RequestInit)?.method === "PUT");
    expect(puts.length).toBe(1);
    expect(JSON.parse((puts[0][1] as RequestInit).body as string)).toEqual({ input_price: "10" });
  });
});
