import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ColumnMapper from "./ColumnMapper";
import type { ColumnMapping } from "../api/catalog";

afterEach(cleanup);

const COLUMNS = [
  { index: 0, header: "Артикул", samples: ["С2000"] },
  { index: 1, header: "Наименование", samples: ["С2000-4"] },
  { index: 2, header: "Цена", samples: ["1234.50"] },
];
const LEVELS = [{ id: 1, name: "Розница", sort_order: 0 }];

const EMPTY: ColumnMapping = {
  name_col: 1, article_col: null, unit_col: null, category_col: null, price_cols: {},
};

describe("ColumnMapper", () => {
  it("renders a select per field and per price level", () => {
    render(<ColumnMapper columns={COLUMNS} levels={LEVELS} mapping={EMPTY} onChange={vi.fn()} />);
    expect(screen.getByLabelText("Наименование")).toBeInTheDocument();
    expect(screen.getByLabelText("Артикул")).toBeInTheDocument();
    expect(screen.getByLabelText("Цена: Розница")).toBeInTheDocument();
  });

  it("emits an updated mapping when a price column is chosen", async () => {
    const onChange = vi.fn();
    render(<ColumnMapper columns={COLUMNS} levels={LEVELS} mapping={EMPTY} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByLabelText("Цена: Розница"), "2");
    const last = onChange.mock.calls.at(-1)?.[0] as ColumnMapping;
    expect(last.price_cols).toEqual({ 1: 2 });
  });

  it("emits article_col = null when '—' is selected", async () => {
    const onChange = vi.fn();
    const withArticle = { ...EMPTY, article_col: 0 };
    render(<ColumnMapper columns={COLUMNS} levels={LEVELS} mapping={withArticle} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByLabelText("Артикул"), "");
    const last = onChange.mock.calls.at(-1)?.[0] as ColumnMapping;
    expect(last.article_col).toBeNull();
  });
});
