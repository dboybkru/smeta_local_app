import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import ShareTab from "./ShareTab";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("ShareTab", () => {
  it("renders export buttons and public links section", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([])));  // listLinks → []
    render(<ShareTab estimateId={7} canEdit={true} />);
    expect(screen.getByText("Скачать Excel")).toBeInTheDocument();
    expect(screen.getByText("Скачать PDF")).toBeInTheDocument();
    expect(await screen.findByText("Публичные ссылки")).toBeInTheDocument();
  });
});
