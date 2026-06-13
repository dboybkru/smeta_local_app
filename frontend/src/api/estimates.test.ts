import { afterEach, describe, expect, it, vi } from "vitest";
import { addLine, createEstimate, listEstimates, patchLine } from "./estimates";

function mockJson(data: unknown, status = 200) {
  return vi.fn(async () =>
    new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } })
  );
}
afterEach(() => vi.restoreAllMocks());

describe("estimates api", () => {
  it("listEstimates GETs /api/estimates", async () => {
    const f = mockJson([]); vi.stubGlobal("fetch", f);
    await listEstimates();
    const calls = f.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/estimates");
  });

  it("createEstimate POSTs body", async () => {
    const f = mockJson({ id: 1 }); vi.stubGlobal("fetch", f);
    await createEstimate({ object_name: "O", vat_enabled: true, vat_rate: "20" });
    const calls = f.mock.calls as unknown as [string, RequestInit][];
    const init = calls[0][1];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ object_name: "O", vat_enabled: true, vat_rate: "20" });
  });

  it("addLine POSTs to the section lines endpoint", async () => {
    const f = mockJson({ id: 9 }); vi.stubGlobal("fetch", f);
    await addLine(5, { item_id: 7, qty: "3" });
    const calls = f.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/sections/5/lines");
    expect(JSON.parse(calls[0][1].body as string)).toEqual({ item_id: 7, qty: "3" });
  });

  it("patchLine PATCHes the line", async () => {
    const f = mockJson({ id: 9 }); vi.stubGlobal("fetch", f);
    await patchLine(9, { qty: "5" });
    const calls = f.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/lines/9");
    expect(calls[0][1].method).toBe("PATCH");
  });
});
