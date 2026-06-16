import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as authModule from "../auth/AuthContext";
import { useEstimate } from "./useEstimate";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
const DETAIL = {
  id: 1, client_id: null, owner_id: 1, object_name: "O", status: "draft",
  vat_enabled: false, vat_rate: "20.00",
  branches: [{ id: 1, name: "Базовая", sections: [] }],
  totals: { sections: [], materials: "0.00", works: "0.00", subtotal: "0.00", vat: "0.00", total: "0.00", purchase: "0.00", margin: "0.00" },
};

function stubRole(role: string) {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role, status: "active", is_superuser: false, org_id: null, org_name: null },
    loginWithPassword: vi.fn(), reload: vi.fn(), logout: vi.fn(),
  });
}

function Probe() {
  const e = useEstimate(1);
  if (!e.estimate) return <div>loading</div>;
  return (
    <div>
      <span data-testid="name">{e.estimate.object_name}</span>
      <span data-testid="canedit">{String(e.canEdit)}</span>
      <button onClick={() => void e.addSection({ name: "Раздел" })}>add</button>
    </div>
  );
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("useEstimate", () => {
  it("loads the estimate and reports canEdit for estimator", async () => {
    stubRole("estimator");
    vi.stubGlobal("fetch", vi.fn(async () => json(DETAIL)));
    render(<Probe />);
    expect(await screen.findByTestId("name")).toHaveTextContent("O");
    expect(screen.getByTestId("canedit")).toHaveTextContent("true");
  });

  it("canEdit is false for viewer", async () => {
    stubRole("viewer");
    vi.stubGlobal("fetch", vi.fn(async () => json(DETAIL)));
    render(<Probe />);
    await screen.findByTestId("name");
    expect(screen.getByTestId("canedit")).toHaveTextContent("false");
  });

  it("addSection POSTs then reloads", async () => {
    stubRole("estimator");
    const f = vi.fn()
      .mockResolvedValueOnce(json(DETAIL))               // initial load
      .mockResolvedValueOnce(json({ id: 2, name: "Раздел", sort_order: 0, markup_percent: "0.00", lines: [] })) // addSection
      .mockResolvedValueOnce(json(DETAIL));              // reload
    vi.stubGlobal("fetch", f);
    render(<Probe />);
    await screen.findByTestId("name");
    await userEvent.click(screen.getByText("add"));
    await waitFor(() => {
      const calls = f.mock.calls.map((c) => c[0] as string);
      expect(calls.filter((u) => u === "/api/estimates/1").length).toBeGreaterThanOrEqual(2);
      expect(calls).toContain("/api/estimates/1/sections");
    });
  });
});
