import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

afterEach(cleanup);
import userEvent from "@testing-library/user-event";
import ColumnMapper from "./ColumnMapper";
import type { Column, ColumnMapping, PriceLevel } from "../api/catalog";

const columns: Column[] = [
  { index: 0, header: "Наименование", samples: ["Кабель"] },
  { index: 1, header: "Производитель", samples: ["ДКС"] },
  { index: 2, header: "РОЗН.", samples: ["100"] },
];
const levels: PriceLevel[] = [{ id: 10, name: "Розница", sort_order: 0 }];

function setup(mapping: ColumnMapping) {
  const onChange = vi.fn();
  render(<ColumnMapper columns={columns} levels={levels} mapping={mapping} onChange={onChange} />);
  return onChange;
}

const base: ColumnMapping = {
  name_col: 0, article_col: null, unit_col: null, category_col: null,
  characteristics_col: null, manufacturer_col: null, price_cols: {},
};

describe("ColumnMapper", () => {
  it("имеет поле Производитель", () => {
    setup(base);
    expect(screen.getByLabelText("Производитель")).toBeInTheDocument();
  });

  it("меняет manufacturer_col", async () => {
    const onChange = setup(base);
    await userEvent.selectOptions(screen.getByLabelText("Производитель"), "1");
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ manufacturer_col: 1 }));
  });

  it("привязывает ценовую колонку к уровню", async () => {
    const onChange = setup(base);
    await userEvent.selectOptions(screen.getByLabelText("Цена: Розница"), "2");
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ price_cols: { 10: 2 } }),
    );
  });
});
