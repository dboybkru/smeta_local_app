import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CatalogSearchInput from "./CatalogSearchInput";

function json(data: unknown) {
  return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
}
const PAGE = {
  items: [{ id: 7, supplier_id: 1, name: "Камера 8Мп", article: "C8", unit: "шт", category: "", kind: "material", prices: { "1": "18700.00" } }],
  total: 1,
};
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("CatalogSearchInput", () => {
  it("searches and calls onPick with the chosen item", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(PAGE)));
    const onPick = vi.fn();
    render(<CatalogSearchInput onPick={onPick} />);
    await userEvent.type(screen.getByPlaceholderText("Поиск позиции в каталоге…"), "камера");
    expect(await screen.findByText("Камера 8Мп")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Камера 8Мп"));
    expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ id: 7, name: "Камера 8Мп" }));
  });
});
