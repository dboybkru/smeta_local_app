import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import CatalogPage from "./CatalogPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
// Routes by URL so the order of the page's parallel loads doesn't matter.
function router(handlers: Record<string, unknown>) {
  return vi.fn(async (url: string) => {
    const key = Object.keys(handlers).find((k) => url.startsWith(k));
    return json(key ? handlers[key] : { detail: "not mocked" }, key ? 200 : 404);
  });
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const LEVELS = [{ id: 1, name: "Розница", sort_order: 0 }];
const SUPPLIERS = [{ id: 1, name: "Болид", column_mapping_template: null }];
const PAGE = {
  items: [
    { id: 7, supplier_id: 1, name: "Прибор приёмно-контрольный", article: "С2000-4", unit: "шт",
      category: "Орион", kind: "material", prices: { "1": "1234.50" } },
  ],
  total: 1,
};

function renderPage() {
  return render(
    <MemoryRouter><AuthProvider><CatalogPage /></AuthProvider></MemoryRouter>
  );
}

describe("CatalogPage", () => {
  it("renders items with a price column per level", async () => {
    vi.stubGlobal("fetch", router({
      "/api/price-levels": LEVELS,
      "/api/suppliers": SUPPLIERS,
      "/api/catalog/items": PAGE,
    }));
    renderPage();
    expect(await screen.findByText("Прибор приёмно-контрольный")).toBeInTheDocument(); // name
    expect(screen.getByText("С2000-4")).toBeInTheDocument(); // article column
    expect(screen.getByText("Розница")).toBeInTheDocument(); // price column header
    expect(screen.getByText("1234.50")).toBeInTheDocument();
  });

  it("passes the search query to the items endpoint", async () => {
    const fetchMock = router({
      "/api/price-levels": LEVELS,
      "/api/suppliers": SUPPLIERS,
      "/api/catalog/items": PAGE,
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    await screen.findByText("Прибор приёмно-контрольный");
    await userEvent.type(screen.getByPlaceholderText("Поиск по названию или артикулу"), "с2000");
    await waitFor(() => {
      const calls = fetchMock.mock.calls.map((c) => c[0] as string);
      expect(calls.some((u) => u.includes("/api/catalog/items?") && u.includes("q=%D1%812000"))).toBe(true);
    });
  });
});
