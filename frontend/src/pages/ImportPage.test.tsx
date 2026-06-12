import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import ImportPage from "./ImportPage";

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
});
