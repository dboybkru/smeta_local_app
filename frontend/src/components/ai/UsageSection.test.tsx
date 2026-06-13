import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UsageSection from "./UsageSection";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const SUMMARY = {
  total_calls: 3,
  total_cost_rub: "0.120000",
  by_model: [
    { provider_name: "AITunnel", model_id: "gpt-4o", calls: 3, prompt_tokens: 100, completion_tokens: 200, cost_rub: "0.120000" },
  ],
};

describe("UsageSection", () => {
  it("shows totals and a per-model row", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(SUMMARY)));
    render(<UsageSection version={0} onChanged={() => {}} />);
    expect(await screen.findByText("gpt-4o")).toBeInTheDocument();
    expect(screen.getByText(/Всего вызовов:/)).toBeInTheDocument();
    expect(screen.getByText("AITunnel")).toBeInTheDocument();
  });

  it("shows empty hint when no usage", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ total_calls: 0, total_cost_rub: null, by_model: [] })));
    render(<UsageSection version={0} onChanged={() => {}} />);
    expect(await screen.findByText(/Расходов пока нет/)).toBeInTheDocument();
  });

  it("clears usage (DELETE) and calls onChanged", async () => {
    const f = vi.fn(async (_url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "DELETE") return new Response(null, { status: 204 });
      return json(SUMMARY);
    });
    vi.stubGlobal("fetch", f);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onChanged = vi.fn();
    render(<UsageSection version={0} onChanged={onChanged} />);
    await screen.findByText("gpt-4o");
    await userEvent.click(screen.getByText("Сбросить"));
    expect(onChanged).toHaveBeenCalled();
    const dels = f.mock.calls.filter((c) => (c[1] as RequestInit)?.method === "DELETE");
    expect(dels.length).toBe(1);
  });
});
