import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SectionTable from "./SectionTable";
import type { SectionDetail, SectionTotals } from "../../api/estimates";

const SECTION = {
  id: 5, name: "Оборудование", sort_order: 0, markup_percent: "10.00",
  lines: [
    { id: 11, section_id: 5, item_id: 7, name: "Камера", unit: "шт", qty: "4.000", work_price: "0.00", material_price: "11000.00", sort_order: 0, purchase_price_snapshot: "7000.00" },
  ],
} as SectionDetail;
const TOTALS = { section_id: 5, materials: "44000.00", works: "0.00", total: "44000.00", purchase: "28000.00", margin: "16000.00" } as SectionTotals;

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function noop() {}

describe("SectionTable", () => {
  it("renders section name, line, and formatted sums", () => {
    render(
      <SectionTable section={SECTION} totals={TOTALS} canEdit showMargin
        onAddLine={vi.fn()} onPatchLine={vi.fn()} onDeleteLine={vi.fn()}
        onPatchSection={vi.fn()} onDeleteSection={noop} />,
    );
    expect(screen.getByDisplayValue("Оборудование")).toBeInTheDocument();
    expect(screen.getByText("Камера")).toBeInTheDocument();
    expect(screen.getByText("16 000,00")).toBeInTheDocument(); // section margin (ru-RU)
  });

  it("calls onPatchLine when qty edited", async () => {
    const onPatchLine = vi.fn();
    render(
      <SectionTable section={SECTION} totals={TOTALS} canEdit showMargin={false}
        onAddLine={vi.fn()} onPatchLine={onPatchLine} onDeleteLine={vi.fn()}
        onPatchSection={vi.fn()} onDeleteSection={noop} />,
    );
    const qty = screen.getByLabelText("Количество строки 11");
    await userEvent.clear(qty);
    await userEvent.type(qty, "6");
    await userEvent.tab();
    expect(onPatchLine).toHaveBeenCalledWith(11, { qty: "6" });
  });

  it("hides margin column when showMargin is false", () => {
    render(
      <SectionTable section={SECTION} totals={TOTALS} canEdit={false} showMargin={false}
        onAddLine={vi.fn()} onPatchLine={vi.fn()} onDeleteLine={vi.fn()}
        onPatchSection={vi.fn()} onDeleteSection={noop} />,
    );
    expect(screen.queryByText("Маржа")).not.toBeInTheDocument();
  });
});
