import { afterEach, expect, it, vi } from "vitest";
import { generateProposal, patchProposal } from "./proposals";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => vi.restoreAllMocks());

it("generateProposal POSTs to generate endpoint", async () => {
  const f = vi.fn(async () => json({ title: "T", subtitle: "", pain: "", solution: "", advantages: [], terms: "", cta: "" }));
  vi.stubGlobal("fetch", f);
  const out = await generateProposal(5);
  expect(out.title).toBe("T");
  const call = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(call[0]).toBe("/api/estimates/5/proposal/generate");
  expect(call[1].method).toBe("POST");
});

it("patchProposal PATCHes partial blocks", async () => {
  const f = vi.fn(async () => json({ title: "New", subtitle: "", pain: "", solution: "", advantages: [], terms: "", cta: "" }));
  vi.stubGlobal("fetch", f);
  const out = await patchProposal(5, { title: "New" });
  expect(out.title).toBe("New");
  const call = f.mock.calls[0] as unknown as [string, RequestInit];
  expect(call[1].method).toBe("PATCH");
  expect(call[1].body).toBe(JSON.stringify({ title: "New" }));
});
