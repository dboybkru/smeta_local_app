import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProposalTab from "./ProposalTab";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
const BLOCKS = { title: "Ремонт под ключ", subtitle: "", pain: "", solution: "", advantages: ["Свои бригады"], terms: "", cta: "" };
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("ProposalTab", () => {
  it("generates blocks via AI and shows them", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.stubGlobal("fetch", vi.fn(async () => json(BLOCKS)));
    render(<ProposalTab estimateId={5} initial={null} canEdit={true} />);
    await userEvent.click(screen.getByText("✨ Сгенерировать AI"));
    expect(await screen.findByDisplayValue("Ремонт под ключ")).toBeInTheDocument();
    expect(screen.getByText("Свои бригады")).toBeInTheDocument();
  });

  it("shows 'AI not configured' banner on 503", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "AI не настроен" }, 503)));
    render(<ProposalTab estimateId={5} initial={null} canEdit={true} />);
    await userEvent.click(screen.getByText("✨ Сгенерировать AI"));
    expect(await screen.findByText(/AI не настроен/)).toBeInTheDocument();
  });

  it("read-only for viewer (no AI button, inputs disabled)", () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(BLOCKS)));
    render(<ProposalTab estimateId={5} initial={BLOCKS} canEdit={false} />);
    expect(screen.queryByText("✨ Сгенерировать AI")).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("Ремонт под ключ")).toBeDisabled();
  });

  it("patches a field on blur", async () => {
    const f = vi.fn(async () => json({ ...BLOCKS, title: "Новый" }));
    vi.stubGlobal("fetch", f);
    render(<ProposalTab estimateId={5} initial={BLOCKS} canEdit={true} />);
    const title = screen.getByDisplayValue("Ремонт под ключ");
    await userEvent.clear(title);
    await userEvent.type(title, "Новый");
    title.blur();
    await vi.waitFor(() => {
      const patched = f.mock.calls.find((c) => ((c as unknown[])[1] as RequestInit | undefined)?.method === "PATCH");
      expect(patched).toBeTruthy();
    });
  });
});
