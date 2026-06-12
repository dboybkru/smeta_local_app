# Phase 2b — Catalog Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the React UI for the catalog backend (Phase 2a): a price-list import wizard, a searchable catalog browser with prices, and a price-levels admin page.

**Architecture:** Add a typed catalog API module (`src/api/catalog.ts`) over the existing `api()` fetch client (extended for multipart upload). Three feature pages (`CatalogPage`, `ImportPage`, `PriceLevelsPage`) plus a shared `AppHeader` for navigation. Admin-only pages are gated by `useAuth().user.role`. Routing is wired in `App.tsx` under the existing `RequireAuth` wrapper. Each page is independently testable with `@testing-library/react` + a mocked `fetch`.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind v4 (stone palette, `font-serif` headings), react-router-dom v7, Vitest + Testing Library.

---

## API contract (Phase 2a — already implemented, do NOT change backend)

All routes are under `/api`. `require_active` = any logged-in active user; `require_admin` = admin only.

| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| GET | `/price-levels` | active | — | `PriceLevel[]` |
| POST | `/price-levels` | admin | `{name, sort_order}` | `PriceLevel` (201); 409 on dup name |
| PATCH | `/price-levels/{id}` | admin | `{name?, sort_order?}` | `PriceLevel`; 409 dup, 404 |
| DELETE | `/price-levels/{id}` | admin | — | 204; 409 if used in prices, 404 |
| GET | `/suppliers` | active | — | `Supplier[]` |
| POST | `/suppliers` | admin | `{name}` | `Supplier` (201); 409 dup |
| POST | `/catalog/inspect` | admin | multipart `file` | `InspectResult` |
| POST | `/catalog/import` | admin | multipart (see below) | `ImportSummary` |
| GET | `/catalog/items?q=&supplier_id=&kind=&limit=&offset=` | active | — | `ItemsPage` |
| GET | `/catalog/items/{id}/prices` | active | — | `PriceHistory[]` |
| GET | `/catalog/price-lists?supplier_id=` | active | — | `PriceList[]` |

`/catalog/import` multipart fields: `file`, `supplier_id` (int), `kind` (`material`|`work`), `sheets` (JSON string array of sheet names), `mapping` (JSON `ColumnMapping`), `use_sheet_as_category` (bool), `save_mapping` (bool).

JSON shapes (note: `prices` keys are stringified level ids, values are decimal **strings**):

```jsonc
// PriceLevel
{ "id": 1, "name": "Розница", "sort_order": 0 }
// Supplier
{ "id": 1, "name": "Болид", "column_mapping_template": { /* ColumnMapping | null */ } }
// InspectResult
{ "sheets": [ { "name": "Лист1", "row_count": 701, "header_row": 0,
  "columns": [ { "index": 0, "header": "Артикул", "samples": ["С2000", "..."] } ] } ] }
// ColumnMapping (price_cols: {price_level_id: column_index})
{ "name_col": 1, "article_col": 0, "unit_col": 3, "category_col": null, "price_cols": { "1": 4, "2": 5 } }
// ImportSummary
{ "price_list_id": 5, "version": 2, "items_created": 12, "items_updated": 688,
  "prices_written": 1382, "price_changes": 40, "rows_skipped": 1, "problems": ["строка 5: ..."] }
// CatalogItem (prices: {level_id_as_string: decimal_string})
{ "id": 7, "supplier_id": 1, "name": "С2000-4", "article": "С2000-4", "unit": "шт",
  "category": "ИСО Орион", "kind": "material", "prices": { "1": "1234.50", "2": "1100.00" } }
// ItemsPage
{ "items": [ /* CatalogItem */ ], "total": 209 }
// PriceList
{ "id": 5, "supplier_id": 1, "filename": "bolid.xlsx", "version": 2, "imported_at": "2026-06-12T09:00:00" }
// PriceHistory
{ "price_list_id": 5, "version": 2, "imported_at": "2026-06-12T09:00:00", "price_level_id": 1, "value": "1234.50" }
```

---

## File Structure

- Create `src/api/catalog.ts` — TS types mirroring the schemas + one async function per endpoint.
- Modify `src/api/client.ts` — let `rawRequest` skip the JSON `Content-Type` for `FormData`; add `apiUpload<T>()`.
- Create `src/components/AppHeader.tsx` — shared header/nav (extracted from `HomePage`), role-gated admin links.
- Modify `src/pages/HomePage.tsx` — use `AppHeader`.
- Create `src/pages/PriceLevelsPage.tsx` — admin CRUD for price levels.
- Create `src/pages/CatalogPage.tsx` — search browser with a price-per-level table.
- Create `src/pages/ImportPage.tsx` — 3-step wizard (Upload → Map → Result).
- Create `src/components/ColumnMapper.tsx` — the column-mapping form used by the wizard's Map step.
- Modify `src/App.tsx` — add `/catalog`, `/import`, `/price-levels` routes under `RequireAuth`.
- Tests colocated: `src/api/catalog.test.ts`, `src/components/AppHeader.test.tsx`, `src/pages/PriceLevelsPage.test.tsx`, `src/pages/CatalogPage.test.tsx`, `src/pages/ImportPage.test.tsx`, `src/components/ColumnMapper.test.tsx`.

**Conventions to follow (from existing code):**
- Pages are default-export function components in `src/pages/`.
- Tailwind stone palette, `font-serif` headings, page wrapper `p-8`, tables `w-full border-collapse text-sm` with `border-b border-stone-200/300`, buttons `rounded border ... px-2 py-1 ... disabled:opacity-50`, errors in `<p role="alert" className="text-red-600">`.
- Errors from `api()`/`apiUpload()` are `ApiError extends Error` — read `err instanceof Error ? err.message : "..."`.
- Tests wrap in `<MemoryRouter><AuthProvider>…</AuthProvider></MemoryRouter>` and mock `global.fetch`.

---

## Task 1: Catalog API module + multipart client support

**Files:**
- Modify: `src/api/client.ts`
- Create: `src/api/catalog.ts`
- Test: `src/api/catalog.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/api/catalog.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { inspectFile, importFile, listItems, listPriceLevels } from "./catalog";

function mockFetchOnce(data: unknown, status = 200) {
  return vi.fn(async () =>
    new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } })
  );
}

afterEach(() => vi.restoreAllMocks());

describe("catalog api", () => {
  it("listItems builds a query string from filters", async () => {
    const fetchMock = mockFetchOnce({ items: [], total: 0 });
    vi.stubGlobal("fetch", fetchMock);
    await listItems({ q: "с2000", supplier_id: 3, kind: "material", limit: 25, offset: 50 });
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/api/catalog/items?");
    expect(url).toContain("q=%D1%812000");
    expect(url).toContain("supplier_id=3");
    expect(url).toContain("kind=material");
    expect(url).toContain("limit=25");
    expect(url).toContain("offset=50");
  });

  it("listPriceLevels GETs the price-levels endpoint", async () => {
    const fetchMock = mockFetchOnce([{ id: 1, name: "Розница", sort_order: 0 }]);
    vi.stubGlobal("fetch", fetchMock);
    const levels = await listPriceLevels();
    expect(levels[0].name).toBe("Розница");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/price-levels");
  });

  it("inspectFile posts FormData without a JSON Content-Type", async () => {
    const fetchMock = mockFetchOnce({ sheets: [] });
    vi.stubGlobal("fetch", fetchMock);
    await inspectFile(new File(["x"], "p.xlsx"));
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBeUndefined();
  });

  it("importFile serializes sheets and mapping as JSON form fields", async () => {
    const fetchMock = mockFetchOnce({
      price_list_id: 1, version: 1, items_created: 1, items_updated: 0,
      prices_written: 1, price_changes: 0, rows_skipped: 0, problems: [],
    });
    vi.stubGlobal("fetch", fetchMock);
    await importFile({
      file: new File(["x"], "p.xlsx"),
      supplier_id: 2,
      kind: "material",
      sheets: ["Лист1"],
      mapping: { name_col: 1, article_col: 0, unit_col: null, category_col: null, price_cols: { 1: 4 } },
      use_sheet_as_category: false,
      save_mapping: true,
    });
    const form = (fetchMock.mock.calls[0][1] as RequestInit).body as FormData;
    expect(form.get("supplier_id")).toBe("2");
    expect(form.get("kind")).toBe("material");
    expect(JSON.parse(form.get("sheets") as string)).toEqual(["Лист1"]);
    expect(JSON.parse(form.get("mapping") as string).price_cols).toEqual({ "1": 4 });
    expect(form.get("save_mapping")).toBe("true");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- catalog.test`
Expected: FAIL — `./catalog` cannot be resolved (module not created yet).

- [ ] **Step 3: Extend the client for multipart**

In `src/api/client.ts`, modify `rawRequest` so it does **not** force a JSON `Content-Type` when the body is `FormData`, and add `apiUpload`. Replace the existing `rawRequest` function with:

```ts
async function rawRequest(path: string, options: RequestInit = {}) {
  const { access } = getTokens();
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  // Browser must set the multipart boundary itself — never force Content-Type for FormData.
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (access) headers["Authorization"] = `Bearer ${access}`;
  return fetch(`${BASE}${path}`, { ...options, headers });
}
```

Then add, at the end of `src/api/client.ts`:

```ts
export async function apiUpload<T = unknown>(path: string, form: FormData): Promise<T> {
  return api<T>(path, { method: "POST", body: form });
}
```

- [ ] **Step 4: Create the catalog API module**

Create `src/api/catalog.ts`:

```ts
import { api, apiUpload } from "./client";

export type PriceLevel = { id: number; name: string; sort_order: number };

export type ColumnMapping = {
  name_col: number;
  article_col: number | null;
  unit_col: number | null;
  category_col: number | null;
  price_cols: Record<number, number>; // price_level_id -> column index
};

export type Supplier = { id: number; name: string; column_mapping_template: ColumnMapping | null };

export type Column = { index: number; header: string; samples: string[] };
export type Sheet = { name: string; row_count: number; header_row: number; columns: Column[] };
export type InspectResult = { sheets: Sheet[] };

export type ImportSummary = {
  price_list_id: number;
  version: number;
  items_created: number;
  items_updated: number;
  prices_written: number;
  price_changes: number;
  rows_skipped: number;
  problems: string[];
};

export type CatalogItem = {
  id: number;
  supplier_id: number;
  name: string;
  article: string;
  unit: string;
  category: string;
  kind: string;
  prices: Record<string, string>; // level_id (string) -> decimal string
};
export type ItemsPage = { items: CatalogItem[]; total: number };

export type PriceList = {
  id: number;
  supplier_id: number;
  filename: string;
  version: number;
  imported_at: string | null;
};

// --- price levels ---
export const listPriceLevels = () => api<PriceLevel[]>("/price-levels");
export const createPriceLevel = (name: string, sort_order: number) =>
  api<PriceLevel>("/price-levels", { method: "POST", body: JSON.stringify({ name, sort_order }) });
export const updatePriceLevel = (id: number, patch: { name?: string; sort_order?: number }) =>
  api<PriceLevel>(`/price-levels/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
export const deletePriceLevel = (id: number) =>
  api<void>(`/price-levels/${id}`, { method: "DELETE" });

// --- suppliers ---
export const listSuppliers = () => api<Supplier[]>("/suppliers");
export const createSupplier = (name: string) =>
  api<Supplier>("/suppliers", { method: "POST", body: JSON.stringify({ name }) });

// --- import ---
export const inspectFile = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiUpload<InspectResult>("/catalog/inspect", form);
};

export type ImportParams = {
  file: File;
  supplier_id: number;
  kind: "material" | "work";
  sheets: string[];
  mapping: ColumnMapping;
  use_sheet_as_category: boolean;
  save_mapping: boolean;
};
export const importFile = (p: ImportParams) => {
  const form = new FormData();
  form.append("file", p.file);
  form.append("supplier_id", String(p.supplier_id));
  form.append("kind", p.kind);
  form.append("sheets", JSON.stringify(p.sheets));
  form.append("mapping", JSON.stringify(p.mapping));
  form.append("use_sheet_as_category", String(p.use_sheet_as_category));
  form.append("save_mapping", String(p.save_mapping));
  return apiUpload<ImportSummary>("/catalog/import", form);
};

// --- catalog browse ---
export type ItemFilters = {
  q?: string;
  supplier_id?: number;
  kind?: string;
  limit?: number;
  offset?: number;
};
export const listItems = (f: ItemFilters = {}) => {
  const params = new URLSearchParams();
  if (f.q) params.set("q", f.q);
  if (f.supplier_id != null) params.set("supplier_id", String(f.supplier_id));
  if (f.kind) params.set("kind", f.kind);
  if (f.limit != null) params.set("limit", String(f.limit));
  if (f.offset != null) params.set("offset", String(f.offset));
  return api<ItemsPage>(`/catalog/items?${params.toString()}`);
};

export const listPriceLists = (supplier_id?: number) => {
  const q = supplier_id != null ? `?supplier_id=${supplier_id}` : "";
  return api<PriceList[]>(`/catalog/price-lists${q}`);
};
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm test -- catalog.test`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/catalog.ts frontend/src/api/catalog.test.ts
git commit -m "feat(catalog-ui): typed catalog API module + multipart upload support"
```

---

## Task 2: Shared AppHeader with role-gated nav

**Files:**
- Create: `src/components/AppHeader.tsx`
- Modify: `src/pages/HomePage.tsx`
- Test: `src/components/AppHeader.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `src/components/AppHeader.test.tsx`:

```tsx
import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppHeader from "./AppHeader";
import * as authModule from "../auth/AuthContext";

function stubUser(role: string) {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role, status: "active" },
    loginWithPassword: vi.fn(),
    acceptTokens: vi.fn(),
    logout: vi.fn(),
  });
}

afterEach(() => vi.restoreAllMocks());

describe("AppHeader", () => {
  it("shows the catalog link to any user", () => {
    stubUser("estimator");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("Каталог")).toBeInTheDocument();
  });

  it("hides admin-only links from non-admins", () => {
    stubUser("estimator");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.queryByText("Импорт")).not.toBeInTheDocument();
    expect(screen.queryByText("Уровни цен")).not.toBeInTheDocument();
  });

  it("shows admin-only links to admins", () => {
    stubUser("admin");
    render(<MemoryRouter><AppHeader /></MemoryRouter>);
    expect(screen.getByText("Импорт")).toBeInTheDocument();
    expect(screen.getByText("Уровни цен")).toBeInTheDocument();
    expect(screen.getByText("Пользователи")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- AppHeader.test`
Expected: FAIL — `./AppHeader` not found.

- [ ] **Step 3: Create AppHeader**

Create `src/components/AppHeader.tsx`:

```tsx
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function AppHeader() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin";
  return (
    <header className="flex items-center justify-between border-b border-stone-200 bg-white px-6 py-3">
      <Link to="/" className="font-serif text-lg text-stone-900">SmetaApp</Link>
      <nav className="flex items-center gap-4 text-sm">
        <Link to="/catalog" className="text-stone-600 hover:text-stone-900">Каталог</Link>
        {isAdmin && (
          <Link to="/import" className="text-stone-600 hover:text-stone-900">Импорт</Link>
        )}
        {isAdmin && (
          <Link to="/price-levels" className="text-stone-600 hover:text-stone-900">Уровни цен</Link>
        )}
        {isAdmin && (
          <Link to="/admin/users" className="text-stone-600 hover:text-stone-900">Пользователи</Link>
        )}
        <span className="text-stone-400">{user?.email}</span>
        <button onClick={logout} className="text-stone-600 hover:text-stone-900">Выйти</button>
      </nav>
    </header>
  );
}
```

- [ ] **Step 4: Refactor HomePage to use AppHeader**

Replace the entire contents of `src/pages/HomePage.tsx` with:

```tsx
import AppHeader from "../components/AppHeader";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8 text-stone-600">
        Каталог и импорт прайсов готовы. Откройте «Каталог» или «Импорт» в меню.
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- AppHeader.test`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AppHeader.tsx frontend/src/components/AppHeader.test.tsx frontend/src/pages/HomePage.tsx
git commit -m "feat(catalog-ui): shared AppHeader with role-gated catalog nav"
```

---

## Task 3: Price Levels admin page

**Files:**
- Create: `src/pages/PriceLevelsPage.tsx`
- Test: `src/pages/PriceLevelsPage.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `src/pages/PriceLevelsPage.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import PriceLevelsPage from "./PriceLevelsPage";

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => vi.restoreAllMocks());

describe("PriceLevelsPage", () => {
  it("lists existing levels", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse([{ id: 1, name: "Розница", sort_order: 0 }])));
    render(<MemoryRouter><PriceLevelsPage /></MemoryRouter>);
    expect(await screen.findByText("Розница")).toBeInTheDocument();
  });

  it("creates a new level and reloads", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([])) // initial load
      .mockResolvedValueOnce(jsonResponse({ id: 2, name: "Опт", sort_order: 1 }, 201)) // create
      .mockResolvedValueOnce(jsonResponse([{ id: 2, name: "Опт", sort_order: 1 }])); // reload
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><PriceLevelsPage /></MemoryRouter>);
    await screen.findByText("Новый уровень");
    await userEvent.type(screen.getByPlaceholderText("Название уровня"), "Опт");
    await userEvent.click(screen.getByText("Добавить"));
    expect(await screen.findByText("Опт")).toBeInTheDocument();
  });

  it("shows the 409 error when a level is in use", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([{ id: 1, name: "Розница", sort_order: 0 }]))
      .mockResolvedValueOnce(jsonResponse({ detail: "Уровень используется в ценах — удалить нельзя" }, 409));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><PriceLevelsPage /></MemoryRouter>);
    await screen.findByText("Розница");
    await userEvent.click(screen.getByText("Удалить"));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("используется в ценах")
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- PriceLevelsPage.test`
Expected: FAIL — `./PriceLevelsPage` not found. (If `@testing-library/user-event` is missing, install it: `npm i -D @testing-library/user-event` — then commit the lockfile in Step 6.)

- [ ] **Step 3: Create the page**

Create `src/pages/PriceLevelsPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import {
  createPriceLevel,
  deletePriceLevel,
  listPriceLevels,
  updatePriceLevel,
  type PriceLevel,
} from "../api/catalog";

export default function PriceLevelsPage() {
  const [levels, setLevels] = useState<PriceLevel[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setLevels(await listPriceLevels());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function add() {
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      await createPriceLevel(name.trim(), levels.length);
      setName("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания");
    } finally {
      setBusy(false);
    }
  }

  async function rename(level: PriceLevel) {
    const next = window.prompt("Новое название уровня", level.name);
    if (!next || next === level.name) return;
    setError("");
    try {
      await updatePriceLevel(level.id, { name: next });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка переименования");
    }
  }

  async function remove(level: PriceLevel) {
    setError("");
    try {
      await deletePriceLevel(level.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    }
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8">
        <h1 className="mb-4 font-serif text-xl text-stone-900">Уровни цен</h1>
        {error && <p role="alert" className="mb-3 text-red-600">{error}</p>}

        <div className="mb-6 flex items-end gap-2">
          <label className="text-sm text-stone-600">
            <span className="mb-1 block">Новый уровень</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название уровня"
              className="rounded border border-stone-300 px-2 py-1"
            />
          </label>
          <button
            onClick={() => void add()}
            disabled={busy}
            className="rounded border border-stone-700 px-3 py-1 text-stone-700 disabled:opacity-50"
          >
            Добавить
          </button>
        </div>

        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-stone-300 text-left text-stone-500">
              <th className="py-2">Порядок</th>
              <th>Название</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {levels.map((l) => (
              <tr key={l.id} className="border-b border-stone-200">
                <td className="py-2 text-stone-400">{l.sort_order}</td>
                <td>{l.name}</td>
                <td className="space-x-2 text-right">
                  <button
                    onClick={() => void rename(l)}
                    className="rounded border border-stone-500 px-2 py-1 text-stone-600"
                  >
                    Переименовать
                  </button>
                  <button
                    onClick={() => void remove(l)}
                    className="rounded border border-red-700 px-2 py-1 text-red-700"
                  >
                    Удалить
                  </button>
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- PriceLevelsPage.test`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PriceLevelsPage.tsx frontend/src/pages/PriceLevelsPage.test.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(catalog-ui): price levels admin page (create/rename/delete)"
```

---

## Task 4: Catalog browser page

**Files:**
- Create: `src/pages/CatalogPage.tsx`
- Test: `src/pages/CatalogPage.test.tsx`

The page loads price levels (for the price columns) and suppliers (for the filter) once, then searches items. Prices render one column per price level, looked up by `prices[String(level.id)]`.

- [ ] **Step 1: Write the failing test**

Create `src/pages/CatalogPage.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import CatalogPage from "./CatalogPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

// Routes by URL so the order of the page's parallel loads doesn't matter.
function router(handlers: Record<string, unknown>) {
  return vi.fn(async (url: string) => {
    const key = Object.keys(handlers).find((k) => url.startsWith(k));
    return json(key ? handlers[key] : { detail: "not mocked" }, key ? 200 : 404);
  });
}

afterEach(() => vi.restoreAllMocks());

const LEVELS = [{ id: 1, name: "Розница", sort_order: 0 }];
const SUPPLIERS = [{ id: 1, name: "Болид", column_mapping_template: null }];
const PAGE = {
  items: [
    { id: 7, supplier_id: 1, name: "С2000-4", article: "С2000-4", unit: "шт",
      category: "Орион", kind: "material", prices: { "1": "1234.50" } },
  ],
  total: 1,
};

describe("CatalogPage", () => {
  it("renders items with a price column per level", async () => {
    vi.stubGlobal("fetch", router({
      "/api/price-levels": LEVELS,
      "/api/suppliers": SUPPLIERS,
      "/api/catalog/items": PAGE,
    }));
    render(<MemoryRouter><CatalogPage /></MemoryRouter>);
    expect(await screen.findByText("С2000-4")).toBeInTheDocument();
    expect(screen.getByText("Розница")).toBeInTheDocument(); // price column header
    expect(screen.getByText("1234.50")).toBeInTheDocument();
  });

  it("passes the search query to the items endpoint", async () => {
    const fetchMock = router({
      "/api/price-levels": LEVELS,
      "/api/suppliers": SUPPLIERS,
      "/api/catalog/items": PAGE,
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><CatalogPage /></MemoryRouter>);
    await screen.findByText("С2000-4");
    await userEvent.type(screen.getByPlaceholderText("Поиск по названию или артикулу"), "с2000");
    await waitFor(() => {
      const calls = fetchMock.mock.calls.map((c) => c[0] as string);
      expect(calls.some((u) => u.includes("/api/catalog/items?") && u.includes("q=%D1%812000"))).toBe(true);
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- CatalogPage.test`
Expected: FAIL — `./CatalogPage` not found.

- [ ] **Step 3: Create the page**

Create `src/pages/CatalogPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import {
  listItems,
  listPriceLevels,
  listSuppliers,
  type CatalogItem,
  type PriceLevel,
  type Supplier,
} from "../api/catalog";

const PAGE_SIZE = 50;

export default function CatalogPage() {
  const [levels, setLevels] = useState<PriceLevel[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [supplierId, setSupplierId] = useState<number | "">("");
  const [kind, setKind] = useState<"" | "material" | "work">("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([listPriceLevels(), listSuppliers()])
      .then(([lv, sp]) => {
        setLevels(lv);
        setSuppliers(sp);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Ошибка загрузки"));
  }, []);

  // Debounced search whenever filters change. Reset offset to 0 on filter change.
  useEffect(() => {
    const handle = setTimeout(() => {
      listItems({
        q: q || undefined,
        supplier_id: supplierId === "" ? undefined : supplierId,
        kind: kind || undefined,
        limit: PAGE_SIZE,
        offset,
      })
        .then((page) => {
          setItems(page.items);
          setTotal(page.total);
        })
        .catch((err) => setError(err instanceof Error ? err.message : "Ошибка поиска"));
    }, 250);
    return () => clearTimeout(handle);
  }, [q, supplierId, kind, offset]);

  function onFilterChange<T>(setter: (v: T) => void) {
    return (value: T) => {
      setOffset(0);
      setter(value);
    };
  }

  const supplierName = (id: number) => suppliers.find((s) => s.id === id)?.name ?? id;

  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8">
        <h1 className="mb-4 font-serif text-xl text-stone-900">Каталог</h1>
        {error && <p role="alert" className="mb-3 text-red-600">{error}</p>}

        <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
          <input
            value={q}
            onChange={(e) => onFilterChange(setQ)(e.target.value)}
            placeholder="Поиск по названию или артикулу"
            className="min-w-64 flex-1 rounded border border-stone-300 px-2 py-1"
          />
          <select
            value={supplierId}
            onChange={(e) => onFilterChange(setSupplierId)(e.target.value === "" ? "" : Number(e.target.value))}
            className="rounded border border-stone-300 px-2 py-1"
          >
            <option value="">Все поставщики</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <select
            value={kind}
            onChange={(e) => onFilterChange(setKind)(e.target.value as "" | "material" | "work")}
            className="rounded border border-stone-300 px-2 py-1"
          >
            <option value="">Материалы и работы</option>
            <option value="material">Материалы</option>
            <option value="work">Работы</option>
          </select>
        </div>

        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-stone-300 text-left text-stone-500">
              <th className="py-2">Артикул</th>
              <th>Наименование</th>
              <th>Поставщик</th>
              <th>Ед.</th>
              {levels.map((l) => (
                <th key={l.id} className="text-right">{l.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.id} className="border-b border-stone-200">
                <td className="py-2 text-stone-500">{it.article || "—"}</td>
                <td className="text-stone-900">{it.name}</td>
                <td className="text-stone-500">{supplierName(it.supplier_id)}</td>
                <td className="text-stone-500">{it.unit}</td>
                {levels.map((l) => (
                  <td key={l.id} className="text-right tabular-nums">
                    {it.prices[String(l.id)] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-4 flex items-center gap-4 text-sm text-stone-500">
          <span>Найдено: {total}</span>
          <button
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0}
            className="rounded border border-stone-300 px-2 py-1 disabled:opacity-40"
          >
            Назад
          </button>
          <span>{Math.floor(offset / PAGE_SIZE) + 1}</span>
          <button
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= total}
            className="rounded border border-stone-300 px-2 py-1 disabled:opacity-40"
          >
            Вперёд
          </button>
        </div>
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- CatalogPage.test`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CatalogPage.tsx frontend/src/pages/CatalogPage.test.tsx
git commit -m "feat(catalog-ui): catalog browser with search, filters, per-level prices"
```

---

## Task 5: ColumnMapper component (wizard Map step)

**Files:**
- Create: `src/components/ColumnMapper.tsx`
- Test: `src/components/ColumnMapper.test.tsx`

A controlled component: receives the chosen sheet's `columns`, the available `levels`, the current `mapping`, and an `onChange(mapping)` callback. Renders a `<select>` per field plus one `<select>` per price level. Column samples are shown under the name field as a lightweight preview.

- [ ] **Step 1: Write the failing test**

Create `src/components/ColumnMapper.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ColumnMapper from "./ColumnMapper";
import type { ColumnMapping } from "../api/catalog";

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- ColumnMapper.test`
Expected: FAIL — `./ColumnMapper` not found.

- [ ] **Step 3: Create the component**

Create `src/components/ColumnMapper.tsx`:

```tsx
import type { Column, ColumnMapping, PriceLevel } from "../api/catalog";

type Props = {
  columns: Column[];
  levels: PriceLevel[];
  mapping: ColumnMapping;
  onChange: (mapping: ColumnMapping) => void;
};

// "" in a <select> means "not mapped" → null (or removed from price_cols).
function parseCol(value: string): number | null {
  return value === "" ? null : Number(value);
}

export default function ColumnMapper({ columns, levels, mapping, onChange }: Props) {
  const options = (
    <>
      <option value="">—</option>
      {columns.map((c) => (
        <option key={c.index} value={c.index}>{c.header}</option>
      ))}
    </>
  );

  function setField(field: "name_col" | "article_col" | "unit_col" | "category_col", value: string) {
    const col = parseCol(value);
    // name_col is required — fall back to the first column if cleared.
    onChange({ ...mapping, [field]: field === "name_col" ? (col ?? 0) : col });
  }

  function setPriceCol(levelId: number, value: string) {
    const next = { ...mapping.price_cols };
    const col = parseCol(value);
    if (col === null) delete next[levelId];
    else next[levelId] = col;
    onChange({ ...mapping, price_cols: next });
  }

  const nameSamples = columns.find((c) => c.index === mapping.name_col)?.samples ?? [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <label className="block">
          <span className="mb-1 block text-stone-600">Наименование</span>
          <select
            aria-label="Наименование"
            value={mapping.name_col}
            onChange={(e) => setField("name_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-stone-600">Артикул</span>
          <select
            aria-label="Артикул"
            value={mapping.article_col ?? ""}
            onChange={(e) => setField("article_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-stone-600">Единица</span>
          <select
            aria-label="Единица"
            value={mapping.unit_col ?? ""}
            onChange={(e) => setField("unit_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-stone-600">Категория</span>
          <select
            aria-label="Категория"
            value={mapping.category_col ?? ""}
            onChange={(e) => setField("category_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
      </div>

      {nameSamples.length > 0 && (
        <p className="text-xs text-stone-400">
          Пример наименований: {nameSamples.slice(0, 3).join(", ")}
        </p>
      )}

      <div>
        <h3 className="mb-2 font-serif text-stone-800">Цены по уровням</h3>
        {levels.length === 0 && (
          <p className="text-sm text-stone-500">
            Нет уровней цен. Сначала создайте их на странице «Уровни цен».
          </p>
        )}
        <div className="grid grid-cols-2 gap-4 text-sm">
          {levels.map((l) => (
            <label key={l.id} className="block">
              <span className="mb-1 block text-stone-600">Цена: {l.name}</span>
              <select
                aria-label={`Цена: ${l.name}`}
                value={mapping.price_cols[l.id] ?? ""}
                onChange={(e) => setPriceCol(l.id, e.target.value)}
                className="w-full rounded border border-stone-300 px-2 py-1"
              >
                {options}
              </select>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- ColumnMapper.test`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ColumnMapper.tsx frontend/src/components/ColumnMapper.test.tsx
git commit -m "feat(catalog-ui): ColumnMapper for mapping file columns to fields and price levels"
```

---

## Task 6: Import wizard page (Upload → Map → Result)

**Files:**
- Create: `src/pages/ImportPage.tsx`
- Test: `src/pages/ImportPage.test.tsx`

A 3-step state machine holding: chosen supplier, kind, file, inspect result, selected sheets, mapping, and the final summary. Step 1 picks supplier/kind/file and calls `inspectFile`. Step 2 selects sheets + maps columns (via `ColumnMapper`, using the first selected sheet's columns) and calls `importFile`. Step 3 shows the `ImportSummary` including `problems[]`.

- [ ] **Step 1: Write the failing test**

Create `src/pages/ImportPage.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ImportPage from "./ImportPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
function router(handlers: Record<string, unknown>) {
  return vi.fn(async (url: string) => {
    const key = Object.keys(handlers).find((k) => url.startsWith(k));
    return json(key ? handlers[key] : { detail: "not mocked" }, key ? 200 : 404);
  });
}

const LEVELS = [{ id: 1, name: "Розница", sort_order: 0 }];
const SUPPLIERS = [{ id: 1, name: "Болид", column_mapping_template: null }];
const INSPECT = {
  sheets: [{
    name: "Лист1", row_count: 2, header_row: 0,
    columns: [
      { index: 0, header: "Артикул", samples: ["С2000"] },
      { index: 1, header: "Наименование", samples: ["С2000-4"] },
      { index: 2, header: "Цена", samples: ["1234.50"] },
    ],
  }],
};
const SUMMARY = {
  price_list_id: 5, version: 1, items_created: 2, items_updated: 0,
  prices_written: 2, price_changes: 0, rows_skipped: 1, problems: ["строка 4: отрицательная цена"],
};

afterEach(() => vi.restoreAllMocks());

describe("ImportPage", () => {
  it("walks upload → map → result and shows problems", async () => {
    vi.stubGlobal("fetch", router({
      "/api/price-levels": LEVELS,
      "/api/suppliers": SUPPLIERS,
      "/api/catalog/inspect": INSPECT,
      "/api/catalog/import": SUMMARY,
    }));
    render(<MemoryRouter><ImportPage /></MemoryRouter>);

    // Step 1: pick supplier, upload file, inspect
    await screen.findByText("Болид"); // supplier option loaded
    await userEvent.selectOptions(screen.getByLabelText("Поставщик"), "1");
    const file = new File(["x"], "bolid.xlsx");
    await userEvent.upload(screen.getByLabelText("Файл прайса"), file);
    await userEvent.click(screen.getByText("Разобрать файл"));

    // Step 2: mapping appears; map name + price, then import
    expect(await screen.findByLabelText("Наименование")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Наименование"), "1");
    await userEvent.selectOptions(screen.getByLabelText("Цена: Розница"), "2");
    await userEvent.click(screen.getByText("Импортировать"));

    // Step 3: summary + problems
    await waitFor(() => expect(screen.getByText(/Импорт завершён/)).toBeInTheDocument());
    expect(screen.getByText(/строка 4: отрицательная цена/)).toBeInTheDocument();
    expect(screen.getByText(/Создано:\s*2/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- ImportPage.test`
Expected: FAIL — `./ImportPage` not found.

- [ ] **Step 3: Create the page**

Create `src/pages/ImportPage.tsx`:

```tsx
import { useEffect, useMemo, useState } from "react";
import AppHeader from "../components/AppHeader";
import ColumnMapper from "../components/ColumnMapper";
import {
  importFile,
  inspectFile,
  listPriceLevels,
  listSuppliers,
  type ColumnMapping,
  type ImportSummary,
  type InspectResult,
  type PriceLevel,
  type Supplier,
} from "../api/catalog";

type Step = "upload" | "map" | "result";

const EMPTY_MAPPING: ColumnMapping = {
  name_col: 0, article_col: null, unit_col: null, category_col: null, price_cols: {},
};

export default function ImportPage() {
  const [step, setStep] = useState<Step>("upload");
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [levels, setLevels] = useState<PriceLevel[]>([]);
  const [supplierId, setSupplierId] = useState<number | "">("");
  const [kind, setKind] = useState<"material" | "work">("material");
  const [file, setFile] = useState<File | null>(null);
  const [inspectResult, setInspectResult] = useState<InspectResult | null>(null);
  const [selectedSheets, setSelectedSheets] = useState<string[]>([]);
  const [mapping, setMapping] = useState<ColumnMapping>(EMPTY_MAPPING);
  const [useSheetAsCategory, setUseSheetAsCategory] = useState(false);
  const [saveMapping, setSaveMapping] = useState(false);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([listSuppliers(), listPriceLevels()])
      .then(([sp, lv]) => {
        setSuppliers(sp);
        setLevels(lv);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Ошибка загрузки"));
  }, []);

  // Columns to map come from the first selected sheet (mapping applies to all selected sheets).
  const mapColumns = useMemo(() => {
    const sheet = inspectResult?.sheets.find((s) => s.name === selectedSheets[0]);
    return sheet?.columns ?? [];
  }, [inspectResult, selectedSheets]);

  async function doInspect() {
    if (supplierId === "" || !file) {
      setError("Выберите поставщика и файл");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await inspectFile(file);
      setInspectResult(res);
      const allSheets = res.sheets.map((s) => s.name);
      setSelectedSheets(allSheets);
      // Prefill mapping from the supplier template if present.
      const tmpl = suppliers.find((s) => s.id === supplierId)?.column_mapping_template;
      setMapping(tmpl ?? EMPTY_MAPPING);
      setStep("map");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось разобрать файл");
    } finally {
      setBusy(false);
    }
  }

  function toggleSheet(name: string) {
    setSelectedSheets((cur) =>
      cur.includes(name) ? cur.filter((n) => n !== name) : [...cur, name]
    );
  }

  async function doImport() {
    if (supplierId === "" || !file || selectedSheets.length === 0) {
      setError("Выберите хотя бы один лист");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await importFile({
        file,
        supplier_id: supplierId,
        kind,
        sheets: selectedSheets,
        mapping,
        use_sheet_as_category: useSheetAsCategory,
        save_mapping: saveMapping,
      });
      setSummary(res);
      setStep("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Импорт не удался");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setStep("upload");
    setFile(null);
    setInspectResult(null);
    setSelectedSheets([]);
    setMapping(EMPTY_MAPPING);
    setSummary(null);
    setError("");
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="max-w-3xl p-8">
        <h1 className="mb-4 font-serif text-xl text-stone-900">Импорт прайса</h1>
        {error && <p role="alert" className="mb-3 text-red-600">{error}</p>}

        {step === "upload" && (
          <div className="space-y-4 text-sm">
            <label className="block">
              <span className="mb-1 block text-stone-600">Поставщик</span>
              <select
                aria-label="Поставщик"
                value={supplierId}
                onChange={(e) => setSupplierId(e.target.value === "" ? "" : Number(e.target.value))}
                className="rounded border border-stone-300 px-2 py-1"
              >
                <option value="">— выберите —</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-stone-600">Тип</span>
              <select
                aria-label="Тип"
                value={kind}
                onChange={(e) => setKind(e.target.value as "material" | "work")}
                className="rounded border border-stone-300 px-2 py-1"
              >
                <option value="material">Материалы</option>
                <option value="work">Работы</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-stone-600">Файл прайса</span>
              <input
                aria-label="Файл прайса"
                type="file"
                accept=".xlsx,.csv"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <button
              onClick={() => void doInspect()}
              disabled={busy}
              className="rounded border border-stone-700 px-3 py-1 text-stone-700 disabled:opacity-50"
            >
              Разобрать файл
            </button>
          </div>
        )}

        {step === "map" && inspectResult && (
          <div className="space-y-6 text-sm">
            <div>
              <h2 className="mb-2 font-serif text-stone-800">Листы</h2>
              {inspectResult.sheets.map((s) => (
                <label key={s.name} className="mr-4 inline-flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={selectedSheets.includes(s.name)}
                    onChange={() => toggleSheet(s.name)}
                  />
                  {s.name} <span className="text-stone-400">({s.row_count})</span>
                </label>
              ))}
            </div>

            <ColumnMapper columns={mapColumns} levels={levels} mapping={mapping} onChange={setMapping} />

            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={useSheetAsCategory}
                  onChange={(e) => setUseSheetAsCategory(e.target.checked)}
                />
                Использовать имя листа как категорию
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={saveMapping}
                  onChange={(e) => setSaveMapping(e.target.checked)}
                />
                Запомнить маппинг для поставщика
              </label>
            </div>

            <div className="space-x-2">
              <button
                onClick={() => setStep("upload")}
                className="rounded border border-stone-400 px-3 py-1 text-stone-600"
              >
                Назад
              </button>
              <button
                onClick={() => void doImport()}
                disabled={busy}
                className="rounded border border-stone-700 px-3 py-1 text-stone-700 disabled:opacity-50"
              >
                Импортировать
              </button>
            </div>
          </div>
        )}

        {step === "result" && summary && (
          <div className="space-y-4 text-sm">
            <h2 className="font-serif text-lg text-stone-900">Импорт завершён</h2>
            <ul className="space-y-1 text-stone-700">
              <li>Версия прайса: {summary.version}</li>
              <li>Создано: {summary.items_created}</li>
              <li>Обновлено: {summary.items_updated}</li>
              <li>Записано цен: {summary.prices_written}</li>
              <li>Изменений цен: {summary.price_changes}</li>
              <li>Пропущено строк: {summary.rows_skipped}</li>
            </ul>
            {summary.problems.length > 0 && (
              <div>
                <h3 className="mb-1 font-serif text-stone-800">
                  Проблемы ({summary.problems.length})
                </h3>
                <ul className="list-inside list-disc text-amber-700">
                  {summary.problems.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </div>
            )}
            <button
              onClick={reset}
              className="rounded border border-stone-700 px-3 py-1 text-stone-700"
            >
              Импортировать ещё
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- ImportPage.test`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ImportPage.tsx frontend/src/pages/ImportPage.test.tsx
git commit -m "feat(catalog-ui): import wizard (upload → map → result with problems)"
```

---

## Task 7: Wire routes + run the full suite

**Files:**
- Modify: `src/App.tsx`
- Test: existing suite (no new test file)

- [ ] **Step 1: Add the routes**

Replace the contents of `src/App.tsx` with:

```tsx
import { Route, Routes } from "react-router-dom";
import RequireAuth from "./components/RequireAuth";
import AdminUsersPage from "./pages/AdminUsersPage";
import AuthCallbackPage from "./pages/AuthCallbackPage";
import CatalogPage from "./pages/CatalogPage";
import HomePage from "./pages/HomePage";
import ImportPage from "./pages/ImportPage";
import LoginPage from "./pages/LoginPage";
import PriceLevelsPage from "./pages/PriceLevelsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/catalog" element={<CatalogPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/price-levels" element={<PriceLevelsPage />} />
        <Route path="/admin/users" element={<AdminUsersPage />} />
      </Route>
    </Routes>
  );
}
```

> Note: `/import` and `/price-levels` are admin-only operations on the backend (`require_admin`). The nav links are already hidden from non-admins by `AppHeader`. The routes themselves are reachable by any active user, but every write call returns 401/403 from the backend, surfaced as an `role="alert"` error. A dedicated admin route-guard is out of scope for this phase (tracked for Phase 3).

- [ ] **Step 2: Run the full test suite**

Run: `cd frontend && npm test`
Expected: PASS — all suites green (LoginPage, catalog api, AppHeader, PriceLevelsPage, CatalogPage, ColumnMapper, ImportPage).

- [ ] **Step 3: Typecheck + build + lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: `tsc -b` and `vite build` succeed with no type errors; eslint reports no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(catalog-ui): route catalog, import, and price-levels pages"
```

---

## Task 8: Manual end-to-end verification + memory update

**Files:** none (verification + docs)

- [ ] **Step 1: Start the dev stack**

```bash
docker compose -f docker-compose.dev.yml up -d
```
Wait for backend (`:8000`) and frontend (`:5173`) to be healthy.

- [ ] **Step 2: Verify in the browser preview**

Use the preview tools (preview_start at `http://localhost:5173`, log in with the dev admin `daniil.gurov@gmail.com` / `Smeta2026!`), then:
1. Open **Уровни цен**, create a level «Розница» (sort_order 0). Confirm it lists.
2. Open **Импорт**: pick a supplier (create «Болид» via the suppliers list / API if none exists), upload a real price file from `D:\git\прайсы` (e.g. `bolid_price.xlsx`), click «Разобрать файл», map Наименование/Артикул/Цена→Розница, click «Импортировать». Confirm the summary shows items_created/prices_written and any `problems[]`.
3. Open **Каталог**, search «С2000», confirm rows + the Розница price column render.

Capture a `preview_screenshot` of the catalog browser with results as proof.

- [ ] **Step 3: Stop the stack**

```bash
docker compose -f docker-compose.dev.yml down
```

- [ ] **Step 4: Update memory**

Update `C:\Users\dboy\.claude\projects\C--Users-dboy--claude\memory\project_smetaapp.md`: mark Phase 2b complete (branch `phase-2b-catalog-frontend`, test count, what shipped), and note the admin route-guard deferral.

- [ ] **Step 5: Final commit (if any docs changed)**

```bash
git add -A && git commit -m "docs: phase 2b complete — catalog frontend"
```

---

## Self-Review

**Spec coverage** (vs the Phase 2a API + the three UI deliverables — import wizard, catalog browser, price-levels admin):
- Import wizard (inspect → mapping → import with `problems[]`): Tasks 5 + 6. ✅
- Catalog browser with search + per-level prices + filters + pagination: Task 4. ✅
- Price-levels admin (create/rename/delete, 409 handling): Task 3. ✅
- Suppliers list + template prefill: used in Tasks 4 & 6 (`listSuppliers`, `column_mapping_template` prefill). ✅
- Multipart upload (inspect/import) over the JSON-only client: Task 1 (`apiUpload`, `FormData` Content-Type fix). ✅
- Role-gated nav: Task 2. ✅
- `price-lists` / per-item price history endpoints: exposed in `catalog.ts` (`listPriceLists`) but no dedicated UI this phase — price history drill-down is deferred to Phase 3 (estimate editor needs it). Noted, not a gap for 2b's stated scope.

**Placeholder scan:** no TBD/TODO-in-code/"add error handling" placeholders; every step ships complete code. ✅

**Type consistency:** `ColumnMapping`, `PriceLevel`, `Supplier`, `InspectResult`, `Sheet`, `Column`, `ImportSummary`, `CatalogItem`, `ItemsPage` are defined once in `src/api/catalog.ts` (Task 1) and imported everywhere else. `price_cols` is `Record<number, number>` throughout; `prices` is `Record<string, string>` (JSON string keys) and is always read via `prices[String(level.id)]`. Function names (`inspectFile`, `importFile`, `listItems`, `listPriceLevels`, `createPriceLevel`, `updatePriceLevel`, `deletePriceLevel`, `listSuppliers`, `createSupplier`, `listPriceLists`) match between definition and use. ✅

**Known deferrals (out of scope for 2b, tracked for Phase 3):** admin route-guard component; supplier create UI inside the wizard (suppliers are managed via the list/API for now); price-history drill-down.
