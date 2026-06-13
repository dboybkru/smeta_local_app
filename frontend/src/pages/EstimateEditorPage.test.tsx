import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import EstimateEditorPage from "./EstimateEditorPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
const DETAIL = {
  id: 1, client_id: null, owner_id: 1, object_name: "Склад", status: "draft",
  vat_enabled: true, vat_rate: "20.00",
  branches: [{ id: 1, name: "Базовая", sections: [
    { id: 5, name: "Оборудование", sort_order: 0, markup_percent: "0.00", lines: [
      { id: 11, section_id: 5, item_id: 7, name: "Камера", unit: "шт", qty: "4.000", work_price: "0.00", material_price: "10000.00", sort_order: 0, purchase_price_snapshot: null },
    ] },
  ] }],
  totals: { sections: [{ section_id: 5, materials: "40000.00", works: "0.00", total: "40000.00", purchase: null, margin: null }],
    materials: "40000.00", works: "0.00", subtotal: "40000.00", vat: "8000.00", total: "48000.00", purchase: null, margin: null },
};
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function renderAt() {
  return render(
    <MemoryRouter initialEntries={["/estimates/1"]}>
      <AuthProvider>
        <Routes><Route path="/estimates/:id" element={<EstimateEditorPage />} /></Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("EstimateEditorPage", () => {
  it("renders header, section, line and totals", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.startsWith("/api/estimates/1")) return json(DETAIL);
      if (url.startsWith("/api/clients")) return json([]);
      return json({ detail: "x" }, 404);
    }));
    renderAt();
    expect(await screen.findByDisplayValue("Склад")).toBeInTheDocument();
    expect(screen.getByText("Камера")).toBeInTheDocument();
    expect(screen.getByText("48 000,00")).toBeInTheDocument(); // total
  });
});
