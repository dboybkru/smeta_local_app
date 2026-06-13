import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import EstimateTotalsBar from "./EstimateTotalsBar";
import type { EstimateTotals } from "../../api/estimates";

const T = {
  sections: [], materials: "40000.00", works: "8000.00", subtotal: "52800.00",
  vat: "10560.00", total: "63360.00", purchase: "28000.00", margin: "24800.00",
} as EstimateTotals;

afterEach(cleanup);

describe("EstimateTotalsBar", () => {
  it("shows total and margin when present", () => {
    render(<EstimateTotalsBar totals={T} vatEnabled />);
    expect(screen.getByText("63 360,00")).toBeInTheDocument();
    expect(screen.getByText(/Маржа/)).toBeInTheDocument();
    expect(screen.getByText("24 800,00")).toBeInTheDocument();
  });

  it("hides margin when null", () => {
    render(<EstimateTotalsBar totals={{ ...T, margin: null, purchase: null }} vatEnabled />);
    expect(screen.queryByText(/Маржа/)).not.toBeInTheDocument();
  });

  it("hides VAT line when disabled", () => {
    render(<EstimateTotalsBar totals={T} vatEnabled={false} />);
    expect(screen.queryByText(/НДС/)).not.toBeInTheDocument();
  });
});
