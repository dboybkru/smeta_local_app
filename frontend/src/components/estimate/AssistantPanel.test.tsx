import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AssistantPanel from "./AssistantPanel";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("AssistantPanel", () => {
  it("sends a message, shows reply + changeset, applies it", async () => {
    const f = vi.fn(async (url: string) => {
      if (url.includes("/assistant/chat"))
        return json({ reply: "Добавил раздел", operations: [{ op: "add_section", name: "Обор" }] });
      if (url.includes("/assistant/apply"))
        return json({ id: 1, branches: [], totals: null });
      return json({});
    });
    vi.stubGlobal("fetch", f);
    const onApplied = vi.fn();
    render(<AssistantPanel estimateId={1} onApplied={onApplied} onClose={() => {}} />);
    await userEvent.type(screen.getByLabelText("Сообщение ассистенту"), "добавь раздел");
    await userEvent.click(screen.getByText("Отправить"));
    expect(await screen.findByText("Добавил раздел")).toBeInTheDocument();
    expect(screen.getByText(/Раздел/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("Применить всё"));
    expect(onApplied).toHaveBeenCalled();
    const applies = f.mock.calls.filter((c) => String(c[0]).includes("/assistant/apply"));
    expect(applies.length).toBe(1);
  });

  it("shows 'AI not configured' on 503", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "не настроен" }, 503)));
    render(<AssistantPanel estimateId={1} onApplied={() => {}} onClose={() => {}} />);
    await userEvent.type(screen.getByLabelText("Сообщение ассистенту"), "hi");
    await userEvent.click(screen.getByText("Отправить"));
    expect(await screen.findByText(/AI не настроен/)).toBeInTheDocument();
  });
});
