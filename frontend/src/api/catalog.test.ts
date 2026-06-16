import { afterEach, describe, expect, it, vi } from "vitest";
import {
  deletePriceLevel,
  importFile,
  inspectFile,
  listItems,
  listPriceLevels,
  type ImportParams,
} from "./catalog";

function mockFetchOnce(data: unknown, status = 200) {
  return vi.fn(async () =>
    new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } })
  );
}

afterEach(() => vi.restoreAllMocks());

describe("catalog api", () => {
  it("listItems builds a query string from filters", async () => {
    const fetchMock = mockFetchOnce({ items: [], total: 0 });
    vi.stubGlobal("fetch", fetchMock);
    await listItems({ q: "с2000", supplier_id: 3, kind: "material", limit: 25, offset: 50 });
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    const url = calls[0][0];
    expect(url).toContain("/api/catalog/items?");
    expect(url).toContain("q=%D1%812000");
    expect(url).toContain("supplier_id=3");
    expect(url).toContain("kind=material");
    expect(url).toContain("limit=25");
    expect(url).toContain("offset=50");
  });

  it("listPriceLevels GETs the price-levels endpoint", async () => {
    const fetchMock = mockFetchOnce([{ id: 1, name: "Розница", sort_order: 0 }]);
    vi.stubGlobal("fetch", fetchMock);
    const levels = await listPriceLevels();
    expect(levels[0].name).toBe("Розница");
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/price-levels");
  });

  it("inspectFile posts FormData without a JSON Content-Type", async () => {
    const fetchMock = mockFetchOnce({ sheets: [] });
    vi.stubGlobal("fetch", fetchMock);
    await inspectFile(new File(["x"], "p.xlsx"));
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    const init = calls[0][1];
    expect(init.body).toBeInstanceOf(FormData);
    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBeUndefined();
  });

  it("importFile отправляет sheet_mappings как JSON form-поле", async () => {
    const fetchMock = mockFetchOnce({
      price_list_id: 1, version: 1, items_created: 1, items_updated: 0,
      prices_written: 1, price_changes: 0, rows_skipped: 0, problems: [],
    });
    vi.stubGlobal("fetch", fetchMock);
    const params: ImportParams = {
      file: new File(["x"], "p.xlsx"),
      supplier_id: 2,
      kind: "material",
      sheet_mappings: [{
        name: "Лист1",
        mapping: {
          name_col: 1, article_col: 0, unit_col: null, category_col: null,
          characteristics_col: null, price_cols: { 1: 4 },
        },
      }],
      use_sheet_as_category: false,
      save_mapping: true,
    };
    await importFile(params);
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    const form = calls[0][1].body as FormData;
    expect(form.get("supplier_id")).toBe("2");
    expect(form.get("kind")).toBe("material");
    const sm = JSON.parse(form.get("sheet_mappings") as string);
    expect(sm[0].name).toBe("Лист1");
    expect(sm[0].mapping.price_cols).toEqual({ "1": 4 });
    expect(form.get("save_mapping")).toBe("true");
  });

  it("deletePriceLevel resolves on a 204 empty response", async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(deletePriceLevel(7)).resolves.toBeUndefined();
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/price-levels/7");
  });
});
