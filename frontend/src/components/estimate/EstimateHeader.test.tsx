import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EstimateHeader from "./EstimateHeader";
import type { EstimateDetail } from "../../api/estimates";

const EST = {
  id: 1, client_id: null, owner_id: 1, object_name: "Склад", status: "draft",
  vat_enabled: false, vat_rate: "20.00", branches: [],
  totals: { sections: [], materials: "0.00", works: "0.00", subtotal: "0.00", vat: "0.00", total: "0.00", purchase: null, margin: null },
} as unknown as EstimateDetail;

afterEach(cleanup);

describe("EstimateHeader", () => {
  it("shows object name and status", () => {
    render(<EstimateHeader estimate={EST} clients={[]} canEdit onPatch={vi.fn()} />);
    expect(screen.getByDisplayValue("Склад")).toBeInTheDocument();
    expect(screen.getByLabelText("Статус")).toHaveValue("draft");
  });

  it("emits patch when VAT toggled", async () => {
    const onPatch = vi.fn();
    render(<EstimateHeader estimate={EST} clients={[]} canEdit onPatch={onPatch} />);
    await userEvent.click(screen.getByLabelText("НДС"));
    expect(onPatch).toHaveBeenCalledWith({ vat_enabled: true });
  });

  it("read-only mode disables inputs for viewer", () => {
    render(<EstimateHeader estimate={EST} clients={[]} canEdit={false} onPatch={vi.fn()} />);
    expect(screen.getByLabelText("Статус")).toBeDisabled();
  });
});
