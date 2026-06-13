# Phase 3b — Estimates Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** React UI for the estimate editor over the Phase 3a backend — list of estimates and an Excel-like single-table editor (view A) with inline catalog search, live totals, and role-aware margin.

**Architecture:** State separated from presentation: a `useEstimate(id)` hook owns the loaded `EstimateDetail` + `totals` and exposes mutations that call the API and reload (backend is the single source of truth for money — no client-side recompute). The view-A table renders over the hook, so other views (B/C) can be added later without touching logic. Money/qty values are JSON strings (Pydantic Decimal) throughout.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind v4, react-router-dom v7, Vitest + @testing-library/react (+ user-event).

---

## Spec reference

Design: `docs/superpowers/specs/2026-06-13-phase3b-estimates-frontend-design.md`. Decisions: view A (single table), inline catalog search + freeform line, reload-after-mutation (no optimistic updates), viewer = read-only, margin shown only when backend returns it.

## Backend API contract (Phase 3a — already shipped, do NOT change)

All under `/api`, all require auth. Money & qty are **strings** in JSON. Margin/purchase fields are `null` for non-owner/non-admin.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/estimates` | — | `EstimateOut[]` |
| POST | `/estimates` | `{object_name, client_id?, vat_enabled?, vat_rate?}` | `EstimateOut` (auto base branch); viewer→403 |
| GET | `/estimates/{id}` | — | `EstimateDetail` (tree + `totals`) |
| PATCH | `/estimates/{id}` | `{object_name?, status?, client_id?, vat_enabled?, vat_rate?}` | `EstimateOut` |
| DELETE | `/estimates/{id}` | — | 204 |
| POST | `/estimates/{id}/sections` | `{name?, markup_percent?}` | `SectionOut` |
| PATCH | `/sections/{id}` | `{name?, sort_order?, markup_percent?}` | `SectionOut` |
| DELETE | `/sections/{id}` | — | 204 |
| POST | `/sections/{id}/lines` | from catalog `{item_id, qty}` OR freeform `{name, unit, qty, work_price?, material_price?, purchase_price_snapshot?}` | `LineOut` |
| PATCH | `/lines/{id}` | `{name?, unit?, qty?, work_price?, material_price?, sort_order?, purchase_price_snapshot?}` | `LineOut` |
| DELETE | `/lines/{id}` | — | 204 |
| GET | `/clients` | — | `ClientOut[]` |
| POST | `/clients` | `{name, default_price_level_id?}` | `ClientOut`; viewer→403 |

JSON shapes (strings for money/qty):
```jsonc
// EstimateOut (list item)
{ "id":1,"client_id":null,"owner_id":3,"object_name":"Объект","status":"draft",
  "vat_enabled":false,"vat_rate":"20.00","branches":[{"id":1,"name":"Базовая","parent_branch_id":null}] }
// EstimateDetail = EstimateOut fields but branches are BranchDetail[] + "totals"
// BranchDetail { id, name, sections: SectionDetail[] }
// SectionDetail { id, name, sort_order, markup_percent, lines: LineDetail[] }
// LineDetail { id, section_id, item_id|null, name, unit, qty, work_price, material_price, sort_order, purchase_price_snapshot|null }
// SectionTotals { section_id, materials, works, total, purchase|null, margin|null }
// EstimateTotals { sections: SectionTotals[], materials, works, subtotal, vat, total, purchase|null, margin|null }
// ClientOut { id, name, default_price_level_id|null, created_at }
```

## Existing frontend to build on

- `src/api/client.ts`: `api<T>(path, options)` — prefixes `/api`, Bearer token, refresh-on-401, 204→undefined, throws `ApiError` (`.message`).
- `src/api/catalog.ts`: `listItems(f: ItemFilters)` → `ItemsPage` (`{items: CatalogItem[], total}`), `CatalogItem` has `prices: Record<string,string>`. Reuse for inline search.
- `src/auth/AuthContext.tsx`: `useAuth()` → `{ user, ... }`, `User = {id,email,name,role,status}`.
- `src/components/AppHeader.tsx`: shared header with role-gated nav links.
- `src/App.tsx`: routes under `<RequireAuth>`.
- **Test conventions (from 2b):** wrap renders in `<MemoryRouter><AuthProvider>…</AuthProvider></MemoryRouter>`; `afterEach(() => { cleanup(); vi.restoreAllMocks(); })`; mock `fetch` via `vi.stubGlobal`. For role-dependent UI, `vi.spyOn(authModule, "useAuth").mockReturnValue({...})`. Money/qty asserted as strings.

## File Structure

- `src/lib/format.ts` — `fmtMoney(s)` Decimal-string → "1 234.50".
- `src/api/estimates.ts` — types + API functions.
- `src/hooks/useEstimate.ts` — load + mutations + reload + `canEdit`.
- `src/pages/EstimatesListPage.tsx`, `src/pages/EstimateEditorPage.tsx`.
- `src/components/estimate/EstimateHeader.tsx`, `CatalogSearchInput.tsx`, `SectionTable.tsx`, `EstimateTotalsBar.tsx`.
- Modify `src/App.tsx` (routes), `src/components/AppHeader.tsx` (link «Сметы»).
- Colocated `*.test.tsx`.

**Conventions:** stone palette, `font-serif` headings, page `min-h-screen bg-stone-50` → `<AppHeader/>` → `<main className="p-8">`, tables `w-full border-collapse text-sm`, inputs/selects `rounded border border-stone-300 px-2 py-1`, errors `<p role="alert" className="text-red-600">`. Run a single test: `cd frontend && npm test -- <pattern>`; full: `npm test`; build `npm run build`; lint `npm run lint`.

---

## Task 1: estimates API module + money formatter

**Files:** Create `src/lib/format.ts`, `src/api/estimates.ts`, `src/api/estimates.test.ts`.

- [ ] **Step 1: Write the failing test** — `frontend/src/api/estimates.test.ts`:

```ts
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
    expect(f.mock.calls[0][0]).toBe("/api/estimates");
  });

  it("createEstimate POSTs body", async () => {
    const f = mockJson({ id: 1 }); vi.stubGlobal("fetch", f);
    await createEstimate({ object_name: "O", vat_enabled: true, vat_rate: "20" });
    const init = f.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ object_name: "O", vat_enabled: true, vat_rate: "20" });
  });

  it("addLine POSTs to the section lines endpoint", async () => {
    const f = mockJson({ id: 9 }); vi.stubGlobal("fetch", f);
    await addLine(5, { item_id: 7, qty: "3" });
    expect(f.mock.calls[0][0]).toBe("/api/sections/5/lines");
    expect(JSON.parse((f.mock.calls[0][1] as RequestInit).body as string)).toEqual({ item_id: 7, qty: "3" });
  });

  it("patchLine PATCHes the line", async () => {
    const f = mockJson({ id: 9 }); vi.stubGlobal("fetch", f);
    await patchLine(9, { qty: "5" });
    expect(f.mock.calls[0][0]).toBe("/api/lines/9");
    expect((f.mock.calls[0][1] as RequestInit).method).toBe("PATCH");
  });
});
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npm test -- estimates.test` → FAIL (module missing).

- [ ] **Step 3: Create the formatter** — `frontend/src/lib/format.ts`:

```ts
// Decimal string "1234.5" → "1 234.50" (ru-RU, non-breaking thin space groups).
export function fmtMoney(value: string | null | undefined): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return n.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
```

- [ ] **Step 4: Create the API module** — `frontend/src/api/estimates.ts`:

```ts
import { api } from "./client";

// Money & qty are JSON strings (backend Decimal).
export type Branch = { id: number; name: string; parent_branch_id: number | null };

export type Estimate = {
  id: number;
  client_id: number | null;
  owner_id: number;
  object_name: string;
  status: string;
  vat_enabled: boolean;
  vat_rate: string;
  branches: Branch[];
};

export type LineDetail = {
  id: number;
  section_id: number;
  item_id: number | null;
  name: string;
  unit: string;
  qty: string;
  work_price: string;
  material_price: string;
  sort_order: number;
  purchase_price_snapshot: string | null;
};
export type SectionDetail = {
  id: number;
  name: string;
  sort_order: number;
  markup_percent: string;
  lines: LineDetail[];
};
export type BranchDetail = { id: number; name: string; sections: SectionDetail[] };

export type SectionTotals = {
  section_id: number;
  materials: string;
  works: string;
  total: string;
  purchase: string | null;
  margin: string | null;
};
export type EstimateTotals = {
  sections: SectionTotals[];
  materials: string;
  works: string;
  subtotal: string;
  vat: string;
  total: string;
  purchase: string | null;
  margin: string | null;
};
export type EstimateDetail = Omit<Estimate, "branches"> & {
  branches: BranchDetail[];
  totals: EstimateTotals;
};

export type Client = {
  id: number;
  name: string;
  default_price_level_id: number | null;
  created_at: string;
};

export type EstimateCreate = {
  object_name: string;
  client_id?: number | null;
  vat_enabled?: boolean;
  vat_rate?: string;
};
export type EstimatePatch = Partial<{
  object_name: string;
  status: string;
  client_id: number | null;
  vat_enabled: boolean;
  vat_rate: string;
}>;
export type LineCreate = {
  item_id?: number;
  name?: string;
  unit?: string;
  qty: string;
  work_price?: string;
  material_price?: string;
  purchase_price_snapshot?: string;
};
export type LinePatch = Partial<{
  name: string;
  unit: string;
  qty: string;
  work_price: string;
  material_price: string;
  sort_order: number;
  purchase_price_snapshot: string;
}>;

const j = (body: unknown) => JSON.stringify(body);

// estimates
export const listEstimates = () => api<Estimate[]>("/estimates");
export const createEstimate = (body: EstimateCreate) =>
  api<Estimate>("/estimates", { method: "POST", body: j(body) });
export const getEstimate = (id: number) => api<EstimateDetail>(`/estimates/${id}`);
export const patchEstimate = (id: number, patch: EstimatePatch) =>
  api<Estimate>(`/estimates/${id}`, { method: "PATCH", body: j(patch) });
export const deleteEstimate = (id: number) =>
  api<void>(`/estimates/${id}`, { method: "DELETE" });

// sections
export const addSection = (estimateId: number, body: { name?: string; markup_percent?: string }) =>
  api<SectionDetail>(`/estimates/${estimateId}/sections`, { method: "POST", body: j(body) });
export const patchSection = (
  id: number,
  patch: Partial<{ name: string; sort_order: number; markup_percent: string }>,
) => api<SectionDetail>(`/sections/${id}`, { method: "PATCH", body: j(patch) });
export const deleteSection = (id: number) =>
  api<void>(`/sections/${id}`, { method: "DELETE" });

// lines
export const addLine = (sectionId: number, body: LineCreate) =>
  api<LineDetail>(`/sections/${sectionId}/lines`, { method: "POST", body: j(body) });
export const patchLine = (id: number, patch: LinePatch) =>
  api<LineDetail>(`/lines/${id}`, { method: "PATCH", body: j(patch) });
export const deleteLine = (id: number) => api<void>(`/lines/${id}`, { method: "DELETE" });

// clients
export const listClients = () => api<Client[]>("/clients");
export const createClient = (name: string, default_price_level_id?: number | null) =>
  api<Client>("/clients", { method: "POST", body: j({ name, default_price_level_id }) });
```

- [ ] **Step 5: Run to verify it passes** — `cd frontend && npm test -- estimates.test` → PASS (4). Then `npm run build` clean.

- [ ] **Step 6: Commit**
```bash
git add frontend/src/lib/format.ts frontend/src/api/estimates.ts frontend/src/api/estimates.test.ts
git commit -m "feat(estimates-ui): typed estimates API module + money formatter"
```

---

## Task 2: useEstimate hook (state + mutations + reload + canEdit)

**Files:** Create `src/hooks/useEstimate.ts`, `src/hooks/useEstimate.test.tsx`.

The hook loads the estimate, exposes `totals`, `canEdit` (role ≠ viewer), and mutation methods that call the API then `reload()`.

- [ ] **Step 1: Write the failing test** — `frontend/src/hooks/useEstimate.test.tsx`:

```tsx
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
    user: { id: 1, email: "a@b.c", name: "A", role, status: "active" },
    loginWithPassword: vi.fn(), acceptTokens: vi.fn(), logout: vi.fn(),
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
      expect(calls.filter((u) => u === "/api/estimates/1").length).toBeGreaterThanOrEqual(2); // load + reload
      expect(calls).toContain("/api/estimates/1/sections");
    });
  });
});
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npm test -- useEstimate.test` → FAIL (module missing).

- [ ] **Step 3: Create the hook** — `frontend/src/hooks/useEstimate.ts`:

```ts
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  addLine as apiAddLine,
  addSection as apiAddSection,
  deleteLine as apiDeleteLine,
  deleteSection as apiDeleteSection,
  getEstimate,
  patchEstimate as apiPatchEstimate,
  patchLine as apiPatchLine,
  patchSection as apiPatchSection,
  type EstimateDetail,
  type EstimatePatch,
  type LineCreate,
  type LinePatch,
} from "../api/estimates";

export function useEstimate(id: number) {
  const { user } = useAuth();
  const [estimate, setEstimate] = useState<EstimateDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      setEstimate(await getEstimate(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Each mutation calls the API then reloads (backend recomputes totals).
  function wrap<A extends unknown[]>(fn: (...a: A) => Promise<unknown>) {
    return async (...a: A) => {
      setError("");
      try {
        await fn(...a);
        await reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Ошибка сохранения");
      }
    };
  }

  return {
    estimate,
    totals: estimate?.totals ?? null,
    loading,
    error,
    reload,
    canEdit: user?.role !== "viewer",
    patchEstimate: wrap((patch: EstimatePatch) => apiPatchEstimate(id, patch)),
    addSection: wrap((body: { name?: string; markup_percent?: string }) => apiAddSection(id, body)),
    patchSection: wrap((sid: number, patch: Parameters<typeof apiPatchSection>[1]) =>
      apiPatchSection(sid, patch),
    ),
    deleteSection: wrap((sid: number) => apiDeleteSection(sid)),
    addLine: wrap((sid: number, body: LineCreate) => apiAddLine(sid, body)),
    patchLine: wrap((lid: number, patch: LinePatch) => apiPatchLine(lid, patch)),
    deleteLine: wrap((lid: number) => apiDeleteLine(lid)),
  };
}
```

- [ ] **Step 4: Run to verify it passes** — `cd frontend && npm test -- useEstimate.test` → PASS (3). `npm run build` clean.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/hooks/useEstimate.ts frontend/src/hooks/useEstimate.test.tsx
git commit -m "feat(estimates-ui): useEstimate hook (load, mutations, reload, canEdit)"
```

---

## Task 3: EstimatesListPage + route + nav link

**Files:** Create `src/pages/EstimatesListPage.tsx`, `src/pages/EstimatesListPage.test.tsx`; Modify `src/App.tsx`, `src/components/AppHeader.tsx`.

- [ ] **Step 1: Write the failing test** — `frontend/src/pages/EstimatesListPage.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import EstimatesListPage from "./EstimatesListPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
function router(map: Record<string, unknown>) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    if ((init?.method ?? "GET") === "POST" && url === "/api/estimates") return json({ id: 99, branches: [] }, 201);
    const k = Object.keys(map).find((x) => url.startsWith(x));
    return json(k ? map[k] : { detail: "x" }, k ? 200 : 404);
  });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function renderPage() {
  return render(<MemoryRouter><AuthProvider><EstimatesListPage /></AuthProvider></MemoryRouter>);
}

const LIST = [{ id: 1, client_id: null, owner_id: 1, object_name: "Склад", status: "draft", vat_enabled: false, vat_rate: "20.00", branches: [] }];

describe("EstimatesListPage", () => {
  it("lists estimates", async () => {
    vi.stubGlobal("fetch", router({ "/api/estimates": LIST, "/api/clients": [] }));
    renderPage();
    expect(await screen.findByText("Склад")).toBeInTheDocument();
  });

  it("creates an estimate", async () => {
    vi.stubGlobal("fetch", router({ "/api/estimates": LIST, "/api/clients": [] }));
    renderPage();
    await screen.findByText("Склад");
    await userEvent.type(screen.getByPlaceholderText("Название объекта"), "Новый объект");
    await userEvent.click(screen.getByText("Создать смету"));
    // навигация на /estimates/99 — проверяем, что POST ушёл
    // (роутер мока вернул id:99; переход проверим интеграционно в Task 9)
  });
});
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npm test -- EstimatesListPage.test` → FAIL.

- [ ] **Step 3: Create the page** — `frontend/src/pages/EstimatesListPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import { useAuth } from "../auth/AuthContext";
import {
  createEstimate,
  deleteEstimate,
  listClients,
  listEstimates,
  type Client,
  type Estimate,
} from "../api/estimates";

export default function EstimatesListPage() {
  const { user } = useAuth();
  const canEdit = user?.role !== "viewer";
  const navigate = useNavigate();
  const [items, setItems] = useState<Estimate[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [name, setName] = useState("");
  const [clientId, setClientId] = useState<number | "">("");
  const [vatEnabled, setVatEnabled] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [est, cl] = await Promise.all([listEstimates(), listClients()]);
      setItems(est);
      setClients(cl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }
  useEffect(() => {
    void load();
  }, []);

  async function create() {
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const est = await createEstimate({
        object_name: name.trim(),
        client_id: clientId === "" ? null : clientId,
        vat_enabled: vatEnabled,
      });
      navigate(`/estimates/${est.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setError("");
    try {
      await deleteEstimate(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить");
    }
  }

  const clientName = (id: number | null) =>
    id == null ? "—" : (clients.find((c) => c.id === id)?.name ?? "—");

  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8">
        <h1 className="mb-4 font-serif text-xl text-stone-900">Сметы</h1>
        {error && <p role="alert" className="mb-3 text-red-600">{error}</p>}

        {canEdit && (
          <div className="mb-6 flex flex-wrap items-end gap-2 text-sm">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название объекта"
              className="min-w-64 rounded border border-stone-300 px-2 py-1"
            />
            <select
              value={clientId}
              onChange={(e) => setClientId(e.target.value === "" ? "" : Number(e.target.value))}
              className="rounded border border-stone-300 px-2 py-1"
            >
              <option value="">Без клиента</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={vatEnabled} onChange={(e) => setVatEnabled(e.target.checked)} />
              НДС
            </label>
            <button
              onClick={() => void create()}
              disabled={busy}
              className="rounded border border-stone-700 px-3 py-1 text-stone-700 disabled:opacity-50"
            >
              Создать смету
            </button>
          </div>
        )}

        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-stone-300 text-left text-stone-500">
              <th className="py-2">Объект</th>
              <th>Клиент</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((e) => (
              <tr key={e.id} className="border-b border-stone-200">
                <td className="py-2">
                  <Link to={`/estimates/${e.id}`} className="text-stone-900 hover:underline">
                    {e.object_name || "Без названия"}
                  </Link>
                </td>
                <td className="text-stone-500">{clientName(e.client_id)}</td>
                <td className="text-stone-500">{e.status}</td>
                <td className="text-right">
                  {canEdit && (
                    <button
                      onClick={() => void remove(e.id)}
                      className="rounded border border-red-700 px-2 py-1 text-red-700"
                    >
                      Удалить
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Add the route** — in `frontend/src/App.tsx` import `EstimatesListPage` and add inside `<RequireAuth>`: `<Route path="/estimates" element={<EstimatesListPage />} />`.

- [ ] **Step 5: Add nav link** — in `frontend/src/components/AppHeader.tsx`, add after the «Каталог» link: `<Link to="/estimates" className="text-stone-600 hover:text-stone-900">Сметы</Link>` (visible to all roles).

- [ ] **Step 6: Run to verify it passes** — `cd frontend && npm test -- EstimatesListPage.test` → PASS. Full suite + build green.

- [ ] **Step 7: Commit**
```bash
git add frontend/src/pages/EstimatesListPage.tsx frontend/src/pages/EstimatesListPage.test.tsx frontend/src/App.tsx frontend/src/components/AppHeader.tsx
git commit -m "feat(estimates-ui): estimates list page + route + nav link"
```

---

## Task 4: EstimateHeader component

**Files:** Create `src/components/estimate/EstimateHeader.tsx`, `src/components/estimate/EstimateHeader.test.tsx`.

Controlled component: props `estimate`, `clients`, `canEdit`, `onPatch(patch)`. Edits object_name (blur), client (select), VAT (checkbox + rate), status (select).

- [ ] **Step 1: Write the failing test** — `frontend/src/components/estimate/EstimateHeader.test.tsx`:

```tsx
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
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npm test -- EstimateHeader.test` → FAIL.

- [ ] **Step 3: Create the component** — `frontend/src/components/estimate/EstimateHeader.tsx`:

```tsx
import { useState } from "react";
import type { Client, EstimateDetail, EstimatePatch } from "../../api/estimates";

type Props = {
  estimate: EstimateDetail;
  clients: Client[];
  canEdit: boolean;
  onPatch: (patch: EstimatePatch) => void;
};

const STATUSES = ["draft", "sent", "approved", "archived"];

export default function EstimateHeader({ estimate, clients, canEdit, onPatch }: Props) {
  const [name, setName] = useState(estimate.object_name);

  return (
    <div className="mb-6 space-y-3">
      <input
        value={name}
        disabled={!canEdit}
        onChange={(e) => setName(e.target.value)}
        onBlur={() => name !== estimate.object_name && onPatch({ object_name: name })}
        className="w-full rounded border border-stone-300 px-2 py-1 font-serif text-xl text-stone-900 disabled:border-transparent disabled:bg-transparent"
        placeholder="Название объекта"
      />
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <label className="flex items-center gap-1">
          <span className="text-stone-500">Клиент</span>
          <select
            aria-label="Клиент"
            disabled={!canEdit}
            value={estimate.client_id ?? ""}
            onChange={(e) => onPatch({ client_id: e.target.value === "" ? null : Number(e.target.value) })}
            className="rounded border border-stone-300 px-2 py-1"
          >
            <option value="">—</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            aria-label="НДС"
            disabled={!canEdit}
            checked={estimate.vat_enabled}
            onChange={(e) => onPatch({ vat_enabled: e.target.checked })}
          />
          НДС
        </label>
        {estimate.vat_enabled && (
          <label className="flex items-center gap-1">
            <span className="text-stone-500">Ставка %</span>
            <input
              aria-label="Ставка НДС"
              disabled={!canEdit}
              defaultValue={estimate.vat_rate}
              onBlur={(e) => e.target.value !== estimate.vat_rate && onPatch({ vat_rate: e.target.value })}
              className="w-16 rounded border border-stone-300 px-2 py-1"
            />
          </label>
        )}
        <label className="flex items-center gap-1">
          <span className="text-stone-500">Статус</span>
          <select
            aria-label="Статус"
            disabled={!canEdit}
            value={estimate.status}
            onChange={(e) => onPatch({ status: e.target.value })}
            className="rounded border border-stone-300 px-2 py-1"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes** — `cd frontend && npm test -- EstimateHeader.test` → PASS (3). Build clean.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/estimate/EstimateHeader.tsx frontend/src/components/estimate/EstimateHeader.test.tsx
git commit -m "feat(estimates-ui): estimate header (name/client/VAT/status)"
```

---

## Task 5: CatalogSearchInput component

**Files:** Create `src/components/estimate/CatalogSearchInput.tsx`, `src/components/estimate/CatalogSearchInput.test.tsx`.

Debounced live search over `listItems`; renders a dropdown; `onPick(item)` fires on selection. Clears query after pick.

- [ ] **Step 1: Write the failing test** — `frontend/src/components/estimate/CatalogSearchInput.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CatalogSearchInput from "./CatalogSearchInput";

function json(data: unknown) {
  return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
}
const PAGE = {
  items: [{ id: 7, supplier_id: 1, name: "Камера 8Мп", article: "C8", unit: "шт", category: "", kind: "material", prices: { "1": "18700.00" } }],
  total: 1,
};
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("CatalogSearchInput", () => {
  it("searches and calls onPick with the chosen item", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(PAGE)));
    const onPick = vi.fn();
    render(<CatalogSearchInput onPick={onPick} />);
    await userEvent.type(screen.getByPlaceholderText("Поиск позиции в каталоге…"), "камера");
    expect(await screen.findByText("Камера 8Мп")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Камера 8Мп"));
    expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ id: 7, name: "Камера 8Мп" }));
  });
});
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npm test -- CatalogSearchInput.test` → FAIL.

- [ ] **Step 3: Create the component** — `frontend/src/components/estimate/CatalogSearchInput.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { listItems, type CatalogItem } from "../../api/catalog";
import { fmtMoney } from "../../lib/format";

type Props = { onPick: (item: CatalogItem) => void };

export default function CatalogSearchInput({ onPick }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<CatalogItem[]>([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    const handle = setTimeout(() => {
      listItems({ q, limit: 8 })
        .then((page) => {
          setResults(page.items);
          setOpen(true);
        })
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(handle);
  }, [q]);

  function pick(item: CatalogItem) {
    onPick(item);
    setQ("");
    setResults([]);
    setOpen(false);
  }

  // first price shown as a hint (level order is backend-defined)
  const firstPrice = (it: CatalogItem) => {
    const vals = Object.values(it.prices);
    return vals.length ? fmtMoney(vals[0]) : "—";
  };

  return (
    <div ref={boxRef} className="relative">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
        placeholder="Поиск позиции в каталоге…"
        className="w-full rounded border border-stone-300 px-2 py-1 text-sm"
      />
      {open && results.length > 0 && (
        <div className="absolute z-10 mt-1 w-full rounded border border-stone-300 bg-white shadow-lg">
          {results.map((it) => (
            <button
              key={it.id}
              type="button"
              onClick={() => pick(it)}
              className="flex w-full items-center justify-between border-b border-stone-100 px-2 py-1 text-left text-sm hover:bg-stone-100"
            >
              <span className="text-stone-800">{it.name}</span>
              <span className="ml-2 shrink-0 tabular-nums text-stone-500">{firstPrice(it)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes** — `cd frontend && npm test -- CatalogSearchInput.test` → PASS. Build clean.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/estimate/CatalogSearchInput.tsx frontend/src/components/estimate/CatalogSearchInput.test.tsx
git commit -m "feat(estimates-ui): inline catalog search input with dropdown"
```

---

## Task 6: SectionTable + LineRow (view A)

**Files:** Create `src/components/estimate/SectionTable.tsx`, `src/components/estimate/SectionTable.test.tsx`.

Renders one section (header with name + markup + delete; line rows; an add-row using `CatalogSearchInput` + «своя строка»). Props: `section`, `sectionTotals`, `levelsCount?` (unused for now), `canEdit`, `showMargin`, and callbacks `onAddLine(body)`, `onPatchLine(id, patch)`, `onDeleteLine(id)`, `onPatchSection(patch)`, `onDeleteSection()`.

- [ ] **Step 1: Write the failing test** — `frontend/src/components/estimate/SectionTable.test.tsx`:

```tsx
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
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npm test -- SectionTable.test` → FAIL.

- [ ] **Step 3: Create the component** — `frontend/src/components/estimate/SectionTable.tsx`:

```tsx
import { useState } from "react";
import type { CatalogItem } from "../../api/catalog";
import type { LineCreate, LineDetail, LinePatch, SectionDetail, SectionTotals } from "../../api/estimates";
import { fmtMoney } from "../../lib/format";
import CatalogSearchInput from "./CatalogSearchInput";

type Props = {
  section: SectionDetail;
  totals: SectionTotals | undefined;
  canEdit: boolean;
  showMargin: boolean;
  onAddLine: (body: LineCreate) => void;
  onPatchLine: (id: number, patch: LinePatch) => void;
  onDeleteLine: (id: number) => void;
  onPatchSection: (patch: Partial<{ name: string; markup_percent: string }>) => void;
  onDeleteSection: () => void;
};

function lineSum(l: LineDetail): string {
  return ((Number(l.work_price) + Number(l.material_price)) * Number(l.qty)).toString();
}

export default function SectionTable({
  section, totals, canEdit, showMargin,
  onAddLine, onPatchLine, onDeleteLine, onPatchSection, onDeleteSection,
}: Props) {
  const [name, setName] = useState(section.name);
  const [markup, setMarkup] = useState(section.markup_percent);
  const [freeform, setFreeform] = useState(false);

  function pick(item: CatalogItem) {
    onAddLine({ item_id: item.id, qty: "1" });
  }

  const colCount = 4 + (showMargin ? 1 : 0) + (canEdit ? 1 : 0);

  return (
    <div className="mb-6">
      <div className="mb-1 flex items-center gap-2">
        <input
          value={name}
          disabled={!canEdit}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => name !== section.name && onPatchSection({ name })}
          className="rounded border border-stone-300 px-2 py-1 font-serif text-stone-800 disabled:border-transparent disabled:bg-transparent"
        />
        {canEdit && (
          <label className="flex items-center gap-1 text-xs text-stone-500">
            наценка %
            <input
              value={markup}
              onChange={(e) => setMarkup(e.target.value)}
              onBlur={() => markup !== section.markup_percent && onPatchSection({ markup_percent: markup })}
              className="w-16 rounded border border-stone-300 px-2 py-1"
            />
          </label>
        )}
        {canEdit && (
          <button onClick={onDeleteSection} className="ml-auto text-xs text-red-700">удалить раздел</button>
        )}
      </div>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-stone-300 text-left text-stone-500">
            <th className="py-1">Наименование</th>
            <th className="w-20 text-right">Кол-во</th>
            <th className="w-24 text-right">Цена</th>
            <th className="w-28 text-right">Сумма</th>
            {showMargin && <th className="w-24 text-right">Маржа</th>}
            {canEdit && <th className="w-8" />}
          </tr>
        </thead>
        <tbody>
          {section.lines.map((l) => {
            const price = (Number(l.work_price) + Number(l.material_price)).toString();
            return (
              <tr key={l.id} className="border-b border-stone-100">
                <td className="py-1 text-stone-800">{l.name}</td>
                <td className="text-right">
                  <input
                    aria-label={`Количество строки ${l.id}`}
                    defaultValue={l.qty}
                    disabled={!canEdit}
                    onBlur={(e) => e.target.value !== l.qty && onPatchLine(l.id, { qty: e.target.value })}
                    className="w-16 rounded border border-stone-200 px-1 py-0.5 text-right tabular-nums disabled:border-transparent"
                  />
                </td>
                <td className="text-right tabular-nums text-stone-500">{fmtMoney(price)}</td>
                <td className="text-right tabular-nums">{fmtMoney(lineSum(l))}</td>
                {showMargin && (
                  <td className="text-right tabular-nums text-green-700">
                    {l.purchase_price_snapshot != null ? fmtMoney(((Number(price) - Number(l.purchase_price_snapshot)) * Number(l.qty)).toString()) : "—"}
                  </td>
                )}
                {canEdit && (
                  <td className="text-right">
                    <button onClick={() => onDeleteLine(l.id)} className="text-red-700">×</button>
                  </td>
                )}
              </tr>
            );
          })}

          {canEdit && (
            <tr>
              <td colSpan={colCount} className="py-2">
                {!freeform ? (
                  <div className="flex items-center gap-2">
                    <div className="flex-1"><CatalogSearchInput onPick={pick} /></div>
                    <button onClick={() => setFreeform(true)} className="text-xs text-stone-500">своя строка</button>
                  </div>
                ) : (
                  <FreeformRow onAdd={(body) => { onAddLine(body); setFreeform(false); }} onCancel={() => setFreeform(false)} />
                )}
              </td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-stone-300 font-medium">
            <td className="py-1" colSpan={3}>Итого по разделу</td>
            <td className="text-right tabular-nums">{fmtMoney(totals?.total)}</td>
            {showMargin && <td className="text-right tabular-nums text-green-700">{fmtMoney(totals?.margin)}</td>}
            {canEdit && <td />}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function FreeformRow({ onAdd, onCancel }: { onAdd: (b: LineCreate) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("шт");
  const [price, setPrice] = useState("");
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Наименование" className="flex-1 rounded border border-stone-300 px-2 py-1" />
      <input value={unit} onChange={(e) => setUnit(e.target.value)} className="w-16 rounded border border-stone-300 px-2 py-1" />
      <input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="цена" className="w-24 rounded border border-stone-300 px-2 py-1" />
      <button
        onClick={() => name.trim() && onAdd({ name: name.trim(), unit, qty: "1", material_price: price || "0" })}
        className="rounded border border-stone-700 px-2 py-1 text-stone-700"
      >
        Добавить
      </button>
      <button onClick={onCancel} className="text-xs text-stone-500">отмена</button>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes** — `cd frontend && npm test -- SectionTable.test` → PASS (3). Build clean.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/estimate/SectionTable.tsx frontend/src/components/estimate/SectionTable.test.tsx
git commit -m "feat(estimates-ui): section table with inline lines, add/edit, freeform"
```

---

## Task 7: EstimateTotalsBar component

**Files:** Create `src/components/estimate/EstimateTotalsBar.tsx`, `src/components/estimate/EstimateTotalsBar.test.tsx`.

- [ ] **Step 1: Write the failing test** — `frontend/src/components/estimate/EstimateTotalsBar.test.tsx`:

```tsx
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
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npm test -- EstimateTotalsBar.test` → FAIL.

- [ ] **Step 3: Create the component** — `frontend/src/components/estimate/EstimateTotalsBar.tsx`:

```tsx
import type { EstimateTotals } from "../../api/estimates";
import { fmtMoney } from "../../lib/format";

type Props = { totals: EstimateTotals; vatEnabled: boolean };

export default function EstimateTotalsBar({ totals, vatEnabled }: Props) {
  return (
    <div className="sticky bottom-0 mt-6 flex flex-wrap items-center justify-end gap-x-6 gap-y-1 border-t border-stone-300 bg-white/95 px-6 py-3 text-sm">
      <span className="text-stone-500">Материалы {fmtMoney(totals.materials)}</span>
      <span className="text-stone-500">Работы {fmtMoney(totals.works)}</span>
      <span className="text-stone-600">Без НДС {fmtMoney(totals.subtotal)}</span>
      {vatEnabled && <span className="text-stone-600">НДС {fmtMoney(totals.vat)}</span>}
      <span className="font-serif text-lg text-stone-900">Всего {fmtMoney(totals.total)}</span>
      {totals.margin != null && (
        <span className="text-green-700">Маржа {fmtMoney(totals.margin)}</span>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes** — `cd frontend && npm test -- EstimateTotalsBar.test` → PASS (3). Build clean.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/estimate/EstimateTotalsBar.tsx frontend/src/components/estimate/EstimateTotalsBar.test.tsx
git commit -m "feat(estimates-ui): floating totals bar with role-aware margin"
```

---

## Task 8: EstimateEditorPage (compose) + route

**Files:** Create `src/pages/EstimateEditorPage.tsx`, `src/pages/EstimateEditorPage.test.tsx`; Modify `src/App.tsx`.

Composes `useEstimate` + the components. Sections live in the base branch (`estimate.branches[0].sections`). `showMargin = totals.margin != null`.

- [ ] **Step 1: Write the failing test** — `frontend/src/pages/EstimateEditorPage.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
```

- [ ] **Step 2: Run to verify it fails** — `cd frontend && npm test -- EstimateEditorPage.test` → FAIL.

- [ ] **Step 3: Create the page** — `frontend/src/pages/EstimateEditorPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import EstimateHeader from "../components/estimate/EstimateHeader";
import EstimateTotalsBar from "../components/estimate/EstimateTotalsBar";
import SectionTable from "../components/estimate/SectionTable";
import { listClients, type Client } from "../api/estimates";
import { useEstimate } from "../hooks/useEstimate";

export default function EstimateEditorPage() {
  const { id } = useParams();
  const estimateId = Number(id);
  const e = useEstimate(estimateId);
  const [clients, setClients] = useState<Client[]>([]);
  const [newSection, setNewSection] = useState("");

  useEffect(() => {
    listClients().then(setClients).catch(() => setClients([]));
  }, []);

  if (e.loading) return <Shell><p className="text-stone-500">Загрузка…</p></Shell>;
  if (e.error || !e.estimate) {
    return <Shell><p role="alert" className="text-red-600">{e.error || "Смета не найдена"}</p></Shell>;
  }

  const est = e.estimate;
  const totals = est.totals;
  const showMargin = totals.margin != null;
  const sections = est.branches[0]?.sections ?? [];
  const sectionTotals = (sid: number) => totals.sections.find((s) => s.section_id === sid);

  return (
    <Shell>
      {e.error && <p role="alert" className="mb-3 text-red-600">{e.error}</p>}
      <EstimateHeader estimate={est} clients={clients} canEdit={e.canEdit} onPatch={e.patchEstimate} />

      {sections.map((s) => (
        <SectionTable
          key={s.id}
          section={s}
          totals={sectionTotals(s.id)}
          canEdit={e.canEdit}
          showMargin={showMargin}
          onAddLine={(body) => e.addLine(s.id, body)}
          onPatchLine={(lid, patch) => e.patchLine(lid, patch)}
          onDeleteLine={(lid) => e.deleteLine(lid)}
          onPatchSection={(patch) => e.patchSection(s.id, patch)}
          onDeleteSection={() => e.deleteSection(s.id)}
        />
      ))}

      {e.canEdit && (
        <div className="mb-6 flex items-center gap-2 text-sm">
          <input
            value={newSection}
            onChange={(ev) => setNewSection(ev.target.value)}
            placeholder="Новый раздел"
            className="rounded border border-stone-300 px-2 py-1"
          />
          <button
            onClick={() => { if (newSection.trim()) { void e.addSection({ name: newSection.trim() }); setNewSection(""); } }}
            className="rounded border border-stone-700 px-3 py-1 text-stone-700"
          >
            + раздел
          </button>
        </div>
      )}

      <EstimateTotalsBar totals={totals} vatEnabled={est.vat_enabled} />
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="mx-auto max-w-4xl p-8">{children}</main>
    </div>
  );
}
```

- [ ] **Step 4: Add the route** — in `frontend/src/App.tsx` import `EstimateEditorPage` and add inside `<RequireAuth>`: `<Route path="/estimates/:id" element={<EstimateEditorPage />} />`.

- [ ] **Step 5: Run to verify it passes** — `cd frontend && npm test -- EstimateEditorPage.test` → PASS. Build clean.

- [ ] **Step 6: Commit**
```bash
git add frontend/src/pages/EstimateEditorPage.tsx frontend/src/pages/EstimateEditorPage.test.tsx frontend/src/App.tsx
git commit -m "feat(estimates-ui): estimate editor page composing header/sections/totals"
```

---

## Task 9: Full suite + build + lint + manual e2e + memory

**Files:** none (verification + docs).

- [ ] **Step 1: Full checks** — `cd frontend && npm test` (all green) · `npm run build` (clean) · `npm run lint` (0 errors; if a new file trips `react-hooks/set-state-in-effect` or similar already-softened rules, that's fine as warnings — do NOT introduce NEW error-level violations).

- [ ] **Step 2: Manual e2e** — bring up the dev stack and verify in the browser preview:
```bash
docker compose -f docker-compose.dev.yml up -d
```
Then (per the 2b playbook): `docker compose -f docker-compose.dev.yml stop frontend` to free 5173, `preview_start smeta-frontend`, log in as the dev admin (`daniil.gurov@gmail.com` / `Smeta2026!`). Verify: open «Сметы», create an estimate, add a section, add a catalog item via inline search (use Bolid data already imported), edit qty, see totals (and margin as owner) update. Capture a `preview_screenshot`. Stop the stack with `docker compose -f docker-compose.dev.yml down` afterward.

- [ ] **Step 3: Update memory** — mark Phase 3b complete in `project_smetaapp.md` (branch, test count, what shipped, deferrals).

- [ ] **Step 4: Commit (if docs changed)** — `git add -A && git commit -m "docs: phase 3b complete — estimate editor frontend"`.

---

## Self-Review

**Spec coverage** (vs `2026-06-13-phase3b-estimates-frontend-design.md`):
- view A single table: Task 6 (SectionTable). ✅
- inline catalog search + freeform: Task 5 + Task 6 (FreeformRow). ✅
- state separated from view via `useEstimate` + reload: Task 2. ✅
- estimates list + create + delete: Task 3. ✅
- header (name/client/VAT/status): Task 4. ✅
- totals bar, margin conditional: Task 7. ✅
- editor composition: Task 8. ✅
- viewer read-only (canEdit gating, margin hidden): Tasks 2/3/4/6/7/8. ✅
- routes + nav link: Tasks 3 & 8. ✅
- reuse `listItems` from 2b: Task 5. ✅
- money/qty as strings, `fmtMoney`: Task 1. ✅
- tests with AuthProvider+cleanup, mock fetch: every task. ✅

**Placeholder scan:** no TBD/"handle errors" placeholders; full code in every step. ✅

**Type consistency:** types defined once in `src/api/estimates.ts` (Task 1) and imported everywhere. `useEstimate` mutation signatures (`addLine(sid, body)`, `patchLine(lid, patch)`, `patchSection(sid, patch)`, `addSection(body)`, `deleteX(id)`, `patchEstimate(patch)`) match their call sites in Tasks 6/8. `LineCreate`/`LinePatch`/`EstimatePatch` names consistent. `fmtMoney` from `src/lib/format.ts` used in Tasks 5/6/7. Money values are strings end-to-end. ✅

**Known deferrals (out of scope for 3b):** multi-view switcher, branch variants, drag-drop reorder, optimistic updates, export (phase 4). Margin per-line in SectionTable is computed client-side **for display only** from backend-provided `purchase_price_snapshot` (which is null for non-owners → shown as "—"); authoritative section/estimate margin always comes from backend `totals`.
