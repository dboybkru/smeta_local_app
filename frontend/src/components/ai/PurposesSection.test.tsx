import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PurposesSection from "./PurposesSection";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const PROV = { id: 1, name: "VseGPT", base_url: "u", auth_style: "x_api_key", enabled: true, has_key: true };
const M = { id: 10, provider_id: 1, model_id: "gpt-4o", label: "GPT-4o", input_price: null, output_price: null, strengths: "", enabled: true };
const PURP = { id: 1, key: "proposal_generation", title: "Генерация КП", description: "", primary_model_id: null, fallback_model_id: null, enabled: true };

function route(url: string) {
  if (url.includes("/ai/purposes")) return json([PURP]);
  if (url.includes("/ai/models")) return json([M]);
  if (url.includes("/ai/providers")) return json([PROV]);
  return json([]);
}

describe("PurposesSection", () => {
  it("selects primary model (PUT)", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PUT") return json({ ...PURP, primary_model_id: 10 });
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<PurposesSection version={0} onChanged={() => {}} />);
    const select = await screen.findByLabelText("Основная модель proposal_generation");
    await userEvent.selectOptions(select, "10");
    const puts = f.mock.calls.filter((c) => (c[1] as RequestInit)?.method === "PUT");
    expect(JSON.parse((puts[0][1] as RequestInit).body as string)).toEqual({ primary_model_id: 10 });
  });

  it("recommends and applies", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/router/recommend")) return json([{ purpose_key: "proposal_generation", provider: "VseGPT", model_id: "gpt-4o", rationale: "хорошо пишет" }]);
      if ((init?.method ?? "GET") === "PUT") return json({ ...PURP, primary_model_id: 10 });
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<PurposesSection version={0} onChanged={() => {}} />);
    await screen.findByText("Генерация КП");
    await userEvent.click(screen.getByText("Подобрать"));
    expect(await screen.findByText(/хорошо пишет/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("Применить"));
    const puts = f.mock.calls.filter((c) => (c[1] as RequestInit)?.method === "PUT");
    expect(JSON.parse((puts[0][1] as RequestInit).body as string)).toEqual({ primary_model_id: 10 });
  });

  it("shows 503 hint when router not configured", async () => {
    const f = vi.fn(async (url: string) => {
      if (url.includes("/router/recommend")) return json({ detail: "router не настроен" }, 503);
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<PurposesSection version={0} onChanged={() => {}} />);
    await screen.findByText("Генерация КП");
    await userEvent.click(screen.getByText("Подобрать"));
    expect(await screen.findByText(/Советник недоступен/)).toBeInTheDocument();
  });
});
