import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ExportButtons from "./ExportButtons";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function stubFetch() {
  const f = vi.fn(async () => new Response(new Blob(["x"]), { status: 200 }));
  vi.stubGlobal("fetch", f);
  vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
  return f;
}

describe("ExportButtons", () => {
  it("downloads xlsx with selected level", async () => {
    const f = stubFetch();
    render(<ExportButtons estimateId={7} />);
    await userEvent.selectOptions(screen.getByLabelText("Уровень"), "cover");
    await userEvent.click(screen.getByText("Скачать Excel"));
    await vi.waitFor(() => {
      expect((f.mock.calls[0] as unknown[])[0]).toBe("/api/estimates/7/export.xlsx?level=cover");
    });
  });

  it("downloads pdf (default level full)", async () => {
    const f = stubFetch();
    render(<ExportButtons estimateId={7} />);
    await userEvent.click(screen.getByText("Скачать PDF"));
    await vi.waitFor(() => {
      expect((f.mock.calls[0] as unknown[])[0]).toBe("/api/estimates/7/export.pdf?level=full");
    });
  });
});
