import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import * as authModule from "../auth/AuthContext";
import ImportPage, { mappingFromDetected } from "./ImportPage";
import type { DetectedLayout, PriceLevel } from "../api/catalog";

const levels: PriceLevel[] = [
  { id: 10, name: "Розница", sort_order: 0 },
  { id: 11, name: "Опт", sort_order: 1 },
];

describe("mappingFromDetected", () => {
  it("строит ColumnMapping и привязывает цены по порядку к уровням", () => {
    const d: DetectedLayout = {
      header_row: 0, data_start_row: 1, name_col: 0, article_col: 1, chars_col: 2,
      unit_col: null, manufacturer_col: null,
      price_columns: [
        { index: 4, label: "Розн", sample: "100", on_request: false },
        { index: 5, label: "Опт", sample: "90", on_request: true },
      ],
      confidence: 0.9,
    };
    const m = mappingFromDetected(d, levels);
    expect(m.name_col).toBe(0);
    expect(m.article_col).toBe(1);
    expect(m.characteristics_col).toBe(2);
    expect(m.header_row).toBe(0);
    expect(m.data_start_row).toBe(1);
    expect(m.price_cols).toEqual({ 10: 4, 11: 5 });
    expect(m.on_request_cols).toEqual([5]);
  });

  it("дефолт name_col=0 если не определён", () => {
    const d: DetectedLayout = {
      header_row: 0, data_start_row: 1, name_col: null, article_col: null,
      chars_col: null, unit_col: null, manufacturer_col: null,
      price_columns: [], confidence: 0,
    };
    expect(mappingFromDetected(d, levels).name_col).toBe(0);
  });
});

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
function router(handlers: Record<string, unknown>) {
  return vi.fn(async (url: string) => {
    const key = Object.keys(handlers).find((k) => url.startsWith(k));
    return json(key ? handlers[key] : { detail: "not mocked" }, key ? 200 : 404);
  });
}

const LEVELS = [{ id: 1, name: "Розница", sort_order: 0 }];
const SUPPLIERS = [{ id: 1, name: "Болид", column_mapping_template: null }];
const INSPECT = {
  sheets: [{
    name: "Лист1", row_count: 2, header_row: 0,
    columns: [
      { index: 0, header: "Артикул", samples: ["С2000"] },
      { index: 1, header: "Наименование", samples: ["С2000-4"] },
      { index: 2, header: "Цена", samples: ["1234.50"] },
    ],
  }],
};
const SUMMARY = {
  price_list_id: 5, version: 1, items_created: 2, items_updated: 0,
  prices_written: 2, price_changes: 0, rows_skipped: 1, problems: ["строка 4: отрицательная цена"],
};

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function renderPage() {
  return render(
    <MemoryRouter><AuthProvider><ImportPage /></AuthProvider></MemoryRouter>
  );
}

describe("ImportPage", () => {
  it("walks upload → map → result and shows problems", async () => {
    vi.stubGlobal("fetch", router({
      "/api/price-levels": LEVELS,
      "/api/suppliers": SUPPLIERS,
      "/api/catalog/inspect": INSPECT,
      "/api/catalog/import": SUMMARY,
    }));
    renderPage();

    // Step 1: pick supplier, upload file, inspect
    await screen.findByText("Болид"); // supplier option loaded
    await userEvent.selectOptions(screen.getByLabelText("Поставщик"), "1");
    const file = new File(["x"], "bolid.xlsx");
    await userEvent.upload(screen.getByLabelText("Файл прайса"), file);
    await userEvent.click(screen.getByText("Разобрать файл"));

    // Step 2: mapping appears; map name + price, then import
    expect(await screen.findByLabelText("Наименование")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Наименование"), "1");
    await userEvent.selectOptions(screen.getByLabelText("Цена: Розница"), "2");
    await userEvent.click(screen.getByText("Импортировать"));

    // Step 3: summary + problems
    await waitFor(() => expect(screen.getByText(/Импорт завершён/)).toBeInTheDocument());
    expect(screen.getByText(/строка 4: отрицательная цена/)).toBeInTheDocument();
    expect(screen.getByText(/Создано:\s*2/)).toBeInTheDocument();
  });

  it("creates a supplier inline and selects it", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST" && url === "/api/suppliers")
        return json({ id: 9, name: "Новый", column_mapping_template: null }, 201);
      if (url.startsWith("/api/suppliers")) return json([]);
      if (url.startsWith("/api/price-levels")) return json([]);
      return json([]);
    });
    vi.stubGlobal("fetch", f);
    vi.spyOn(authModule, "useAuth").mockReturnValue({
      user: { id: 1, email: "a@b.c", name: "A", role: "admin", status: "active", is_superuser: false, org_id: null, org_name: null },
      loginWithPassword: vi.fn(), reload: vi.fn(), logout: vi.fn(),
    });
    render(<MemoryRouter><AuthProvider><ImportPage /></AuthProvider></MemoryRouter>);
    await userEvent.click(await screen.findByText("+ новый"));
    await userEvent.type(screen.getByPlaceholderText("Имя поставщика"), "Новый");
    await userEvent.click(screen.getByText("Создать"));
    const select = await screen.findByLabelText("Поставщик");
    expect((select as HTMLSelectElement).value).toBe("9");
    expect(await screen.findByRole("option", { name: "Новый" })).toBeInTheDocument();
  });
});
