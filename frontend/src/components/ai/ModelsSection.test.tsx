import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ModelsSection from "./ModelsSection";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const PROV = { id: 1, name: "VseGPT", base_url: "u", auth_style: "x_api_key", enabled: true, has_key: true };
const ON = { id: 10, provider_id: 1, model_id: "gpt-4o", label: "GPT-4o", input_price: null, output_price: null, strengths: "", enabled: true };
const OFF = { id: 11, provider_id: 1, model_id: "gpt-4o-mini", label: "GPT-4o-mini", input_price: null, output_price: null, strengths: "", enabled: false };

function route(url: string) {
  if (url.includes("/ai/providers")) return json([PROV]);
  if (url.includes("/ai/models")) return json([ON, OFF]);
  return json([]);
}

describe("ModelsSection", () => {
  it("lists only enabled models, hides disabled ones from the table", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => route(url)));
    render(<ModelsSection version={0} onChanged={() => {}} />);
    expect(await screen.findByText("gpt-4o")).toBeInTheDocument(); // enabled, in table
    expect(screen.queryByText("gpt-4o-mini")).not.toBeInTheDocument(); // disabled, not in table
  });

  it("search shows a dropdown; clicking a result enables it (PUT)", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PUT") return json({ ...OFF, enabled: true });
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<ModelsSection version={0} onChanged={() => {}} />);
    await screen.findByText("gpt-4o");
    await userEvent.type(screen.getByLabelText("Поиск модели"), "mini");
    await userEvent.click(await screen.findByText("GPT-4o-mini")); // dropdown item
    const puts = f.mock.calls.filter((c) => (c[1] as RequestInit)?.method === "PUT");
    expect(puts.length).toBe(1);
    expect(JSON.parse((puts[0][1] as RequestInit).body as string)).toEqual({ enabled: true });
  });

  it("shows 'not found' in the dropdown for a non-matching query", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => route(url)));
    render(<ModelsSection version={0} onChanged={() => {}} />);
    await screen.findByText("gpt-4o");
    await userEvent.type(screen.getByLabelText("Поиск модели"), "zzz");
    expect(await screen.findByText(/Ничего не найдено/)).toBeInTheDocument();
  });

  it("runs a per-model smoke test and shows the result", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST" && url.includes("/models/10/test"))
        return json({ ok: true, detail: "" });
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<ModelsSection version={0} onChanged={() => {}} />);
    await screen.findByText("gpt-4o");
    await userEvent.click(screen.getByText("Тест"));
    expect(await screen.findByText("✓")).toBeInTheDocument();
    const posts = f.mock.calls.filter((c) => ((c[1] as RequestInit)?.method ?? "GET") === "POST");
    expect(posts.some((c) => String(c[0]).includes("/models/10/test"))).toBe(true);
  });

  it("deletes all models (bulk DELETE) and calls onChanged", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "DELETE") return json({ deleted: 2 });
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onChanged = vi.fn();
    render(<ModelsSection version={0} onChanged={onChanged} />);
    await userEvent.click(await screen.findByText("Удалить все"));
    expect(onChanged).toHaveBeenCalled();
    const dels = f.mock.calls.filter((c) => (c[1] as RequestInit)?.method === "DELETE");
    expect(dels.length).toBe(1);
    expect(String(dels[0][0])).toMatch(/\/ai\/models$/);
  });

  it("saves input price on blur for an enabled model (PUT)", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PUT") return json({ ...ON, input_price: "10" });
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<ModelsSection version={0} onChanged={() => {}} />);
    const input = await screen.findByLabelText("Вход gpt-4o");
    await userEvent.type(input, "10");
    await userEvent.tab();
    const puts = f.mock.calls.filter((c) => (c[1] as RequestInit)?.method === "PUT");
    expect(puts.length).toBe(1);
    expect(JSON.parse((puts[0][1] as RequestInit).body as string)).toEqual({ input_price: "10" });
  });
});
