import { describe, expect, it, vi, beforeEach } from "vitest";
import { importFile, type ImportParams } from "./catalog";

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.setItem("access_token", "t");
});

describe("importFile", () => {
  it("отправляет sheet_mappings как JSON", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ price_list_id: 1, version: 1, items_created: 1,
        items_updated: 0, prices_written: 1, price_changes: 0, rows_skipped: 0,
        problems: [] }), { status: 200 }),
    );
    const params: ImportParams = {
      file: new File(["x"], "p.xlsx"),
      supplier_id: 1,
      kind: "material",
      sheet_mappings: [{ name: "Sheet", mapping: { name_col: 0, article_col: null,
        unit_col: null, category_col: null, characteristics_col: null, price_cols: {} } }],
      use_sheet_as_category: false,
      save_mapping: false,
    };
    await importFile(params);
    const body = spy.mock.calls[0][1]!.body as FormData;
    expect(body.get("sheet_mappings")).toContain("\"name\":\"Sheet\"");
  });
});
