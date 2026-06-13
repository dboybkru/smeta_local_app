# Фаза 4b-2a — Управление поставщиками Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** UI для заведения поставщиков: страница `/admin/suppliers` (список + добавить) и инлайн-создание в мастере импорта (закрывает блокер пустого списка).

**Architecture:** Бэкенд без изменений (`GET`/`POST /api/suppliers` уже есть). `api/catalog.ts` уже экспортирует `listSuppliers`/`createSupplier` — API-слой готов. Две UI-задачи: новая страница `SuppliersPage` (по образцу `PriceLevelsPage`) + инлайн-создание в `ImportPage`.

**Tech Stack:** React 19 + TypeScript + Vite + Tailwind v4 + react-router v7; Vitest + @testing-library/react + userEvent.

---

## Соглашения

- API уже есть: `listSuppliers()` → `Supplier[]`, `createSupplier(name)` → `Supplier` (`api/catalog.ts`). `Supplier = { id, name, column_mapping_template }`. `ApiError` (`api/client.ts`) несёт `.status` (409 при дубле имени).
- Доступ: admin (как «Импорт»/«Уровни цен»; бэкенд `POST /suppliers` уже `require_admin`).
- Тесты (Vitest): паттерн 3b/4b-1 — `json()`-хелпер, `vi.stubGlobal("fetch", …)`, `vi.spyOn(authModule,"useAuth").mockReturnValue({user, loginWithPassword, acceptTokens, logout})`, рендер `<MemoryRouter><AuthProvider>…`, `afterEach(cleanup; vi.restoreAllMocks)`.
- Запуск: `cd frontend && npm run test -- <file>`; `npm run build`; `npm run lint`.

## File Structure

| Файл | Ответственность |
|---|---|
| `frontend/src/pages/SuppliersPage.tsx` | `/admin/suppliers`: список + добавить (409-сообщение) |
| `frontend/src/App.tsx` | + маршрут `/admin/suppliers` |
| `frontend/src/components/AppHeader.tsx` | + ссылка «Поставщики» (admin) |
| `frontend/src/pages/ImportPage.tsx` | инлайн «+ новый поставщик» у дропдауна |
| тесты | `SuppliersPage.test.tsx`; кейсы в `ImportPage.test.tsx` |

---

## Task 1: Страница поставщиков + маршрут + ссылка

**Files:**
- Create: `frontend/src/pages/SuppliersPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppHeader.tsx`
- Test: `frontend/src/pages/SuppliersPage.test.tsx`

- [ ] **Step 1: Failing test** — `frontend/src/pages/SuppliersPage.test.tsx`:
```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import * as authModule from "../auth/AuthContext";
import SuppliersPage from "./SuppliersPage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function stubAdmin() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role: "admin", status: "active" },
    loginWithPassword: vi.fn(), acceptTokens: vi.fn(), logout: vi.fn(),
  });
}
function renderPage() {
  return render(<MemoryRouter><AuthProvider><SuppliersPage /></AuthProvider></MemoryRouter>);
}
const SUP = { id: 1, name: "Optimus", column_mapping_template: null };

describe("SuppliersPage", () => {
  it("lists suppliers", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([SUP])));
    stubAdmin(); renderPage();
    expect(await screen.findByText("Optimus")).toBeInTheDocument();
  });

  it("shows empty hint when none", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([])));
    stubAdmin(); renderPage();
    expect(await screen.findByText(/Поставщиков пока нет/)).toBeInTheDocument();
  });

  it("creates a supplier (POST) and shows it", async () => {
    const f = vi.fn(async (_url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") return json({ id: 2, name: "Bolid", column_mapping_template: null }, 201);
      return json([]);
    });
    vi.stubGlobal("fetch", f);
    stubAdmin(); renderPage();
    await screen.findByText(/Поставщиков пока нет/);
    await userEvent.type(screen.getByPlaceholderText("Название"), "Bolid");
    await userEvent.click(screen.getByText("Добавить"));
    expect(await screen.findByText("Bolid")).toBeInTheDocument();
  });

  it("shows 409 message on duplicate name", async () => {
    const f = vi.fn(async (_url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") return json({ detail: "Поставщик существует" }, 409);
      return json([]);
    });
    vi.stubGlobal("fetch", f);
    stubAdmin(); renderPage();
    await screen.findByText(/Поставщиков пока нет/);
    await userEvent.type(screen.getByPlaceholderText("Название"), "Optimus");
    await userEvent.click(screen.getByText("Добавить"));
    expect(await screen.findByText(/уже существует/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run, confirm FAIL** — `npm run test -- src/pages/SuppliersPage.test.tsx`

- [ ] **Step 3: Create `frontend/src/pages/SuppliersPage.tsx`:**
```tsx
import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import { ApiError } from "../api/client";
import { createSupplier, listSuppliers, type Supplier } from "../api/catalog";

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setSuppliers(await listSuppliers());
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
      await createSupplier(name.trim());
      setName("");
      await load();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError("Поставщик с таким именем уже существует");
      } else {
        setError(err instanceof Error ? err.message : "Ошибка создания");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8">
        <h1 className="mb-4 font-serif text-xl text-stone-900">Поставщики</h1>
        {error && <p role="alert" className="mb-3 text-red-600">{error}</p>}

        <div className="mb-6 flex items-end gap-2">
          <label className="text-sm text-stone-600">
            <span className="mb-1 block">Новый поставщик</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название"
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

        {suppliers.length === 0 ? (
          <p className="text-sm text-stone-500">Поставщиков пока нет — добавьте первого.</p>
        ) : (
          <ul className="grid gap-1 text-sm">
            {suppliers.map((s) => (
              <li key={s.id} className="border-b border-stone-200 py-2 text-stone-700">{s.name}</li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Route** — в `frontend/src/App.tsx`: добавить `import SuppliersPage from "./pages/SuppliersPage";` и внутри `<RequireAuth>` `<Route path="/admin/suppliers" element={<SuppliersPage />} />`.

- [ ] **Step 5: Header link** — в `frontend/src/components/AppHeader.tsx`, в admin-секции (рядом с «Уровни цен»), добавить:
```tsx
        {isAdmin && (
          <Link to="/admin/suppliers" className="text-stone-600 hover:text-stone-900">Поставщики</Link>
        )}
```
(вставить сразу после блока ссылки «Уровни цен» `{isAdmin && (<Link to="/price-levels" …>Уровни цен</Link>)}`)

- [ ] **Step 6: Run, confirm PASS** — `npm run test -- src/pages/SuppliersPage.test.tsx` (4 passed)

- [ ] **Step 7: Commit**
```bash
git add frontend/src/pages/SuppliersPage.tsx frontend/src/App.tsx frontend/src/components/AppHeader.tsx frontend/src/pages/SuppliersPage.test.tsx
git commit -m "feat(4b2a): suppliers page (/admin/suppliers) + header link + route"
```

---

## Task 2: Инлайн-создание поставщика в мастере импорта

**Files:**
- Modify: `frontend/src/pages/ImportPage.tsx`
- Test: `frontend/src/pages/ImportPage.test.tsx` (добавить кейс)

Текущее состояние `ImportPage` (шаг "upload"): `<select aria-label="Поставщик">` со списком `suppliers` и опцией «— выберите —». Импортированы `listSuppliers`, тип `Supplier` из `../api/catalog`. Состояние `suppliers`, `supplierId`.

- [ ] **Step 1: Failing test** — добавить в `frontend/src/pages/ImportPage.test.tsx` новый кейс (используй существующие в файле хелперы `json`/`stubUser`/рендер; если их нет — добавь по образцу ниже):
```tsx
// при необходимости — импорты и хелперы (если в файле их ещё нет):
// import { afterEach, describe, expect, it, vi } from "vitest";
// import { cleanup, render, screen } from "@testing-library/react";
// import userEvent from "@testing-library/user-event";
// import { MemoryRouter } from "react-router-dom";
// import { AuthProvider } from "../auth/AuthContext";
// import * as authModule from "../auth/AuthContext";
// import ImportPage from "./ImportPage";
// function json(d:unknown,s=200){return new Response(JSON.stringify(d),{status:s,headers:{"Content-Type":"application/json"}});}

it("creates a supplier inline and selects it", async () => {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    if ((init?.method ?? "GET") === "POST" && url === "/api/suppliers")
      return json({ id: 9, name: "Новый", column_mapping_template: null }, 201);
    if (url.startsWith("/api/suppliers")) return json([]);
    if (url.startsWith("/api/price-levels")) return json([]);
    return json([]);
  });
  vi.stubGlobal("fetch", f);
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role: "admin", status: "active" },
    loginWithPassword: vi.fn(), acceptTokens: vi.fn(), logout: vi.fn(),
  });
  render(<MemoryRouter><AuthProvider><ImportPage /></AuthProvider></MemoryRouter>);
  await userEvent.click(await screen.findByText("+ новый"));
  await userEvent.type(screen.getByPlaceholderText("Имя поставщика"), "Новый");
  await userEvent.click(screen.getByText("Создать"));
  // новый поставщик появился в дропдауне и выбран
  const select = await screen.findByLabelText("Поставщик");
  expect((select as HTMLSelectElement).value).toBe("9");
  expect(await screen.findByRole("option", { name: "Новый" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run, confirm FAIL** — `npm run test -- src/pages/ImportPage.test.tsx`

- [ ] **Step 3: Implement inline-create in `ImportPage.tsx`**
1. Расширить импорт из `../api/catalog`: добавить `createSupplier` к существующему списку (`importFile, inspectFile, listPriceLevels, listSuppliers, createSupplier, type ...`). Добавить `import { ApiError } from "../api/client";`.
2. Добавить состояние рядом с другими `useState` (после `const [supplierId, setSupplierId] = useState<number | "">("");`):
```tsx
  const [creatingSupplier, setCreatingSupplier] = useState(false);
  const [newSupplierName, setNewSupplierName] = useState("");
```
3. Добавить функцию (рядом с `doInspect`):
```tsx
  async function addSupplier() {
    const nm = newSupplierName.trim();
    if (!nm) return;
    setError("");
    try {
      const sup = await createSupplier(nm);
      setSuppliers((cur) => [...cur, sup]);
      setSupplierId(sup.id);
      setNewSupplierName("");
      setCreatingSupplier(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setError("Поставщик с таким именем уже существует");
      else setError(err instanceof Error ? err.message : "Ошибка создания поставщика");
    }
  }
```
4. В шаге "upload", внутри `<label>` поставщика, после `</select>` добавить переключатель и инлайн-форму:
```tsx
              </select>
              {!creatingSupplier ? (
                <button
                  type="button"
                  onClick={() => setCreatingSupplier(true)}
                  className="ml-2 text-stone-600 underline"
                >
                  + новый
                </button>
              ) : (
                <span className="ml-2 inline-flex items-center gap-1">
                  <input
                    aria-label="Имя поставщика"
                    value={newSupplierName}
                    onChange={(e) => setNewSupplierName(e.target.value)}
                    placeholder="Имя поставщика"
                    className="rounded border border-stone-300 px-2 py-1"
                  />
                  <button type="button" onClick={() => void addSupplier()} className="rounded border border-stone-700 px-2 py-1 text-stone-700">Создать</button>
                  <button type="button" onClick={() => { setCreatingSupplier(false); setNewSupplierName(""); }} className="text-stone-500">Отмена</button>
                </span>
              )}
```
(вставка идёт сразу после закрывающего тега `</select>` внутри `<label><span>Поставщик</span> … </label>` — кнопка/форма оказываются на той же строке, что и дропдаун.)

- [ ] **Step 4: Run, confirm PASS** — `npm run test -- src/pages/ImportPage.test.tsx`

- [ ] **Step 5: Run full + build + lint**
- `npm run test` (все зелёные)
- `npm run build` (чисто)
- `npm run lint` (0 errors; set-state-in-effect warnings ок)

- [ ] **Step 6: Commit**
```bash
git add frontend/src/pages/ImportPage.tsx frontend/src/pages/ImportPage.test.tsx
git commit -m "feat(4b2a): inline supplier creation in import wizard"
```

---

## Финальная проверка

- [ ] `cd frontend && npm run test` зелёно; `npm run build` чисто; `npm run lint` 0 errors.
- [ ] Живой e2e: `/admin/suppliers` — добавить поставщика; мастер импорта `/import` — «+ новый», создать, выбрать, дойти до разбора файла (проверка, что блокер снят).
- [ ] Merge в `main` + push; redeploy прода.

## Self-Review (выполнено автором)

**Покрытие спека:** страница `/admin/suppliers` список+создание+409 (Task 1) ✓; ссылка «Поставщики» admin (Task 1) ✓; маршрут (Task 1) ✓; инлайн-создание в импорте + выбор нового (Task 2) ✓; бэкенд без изменений ✓ (createSupplier/listSuppliers уже в `api/catalog.ts` — добавлять не нужно); удаление/авто-парс отложены ✓.

**Согласованность типов:** `Supplier`/`createSupplier`/`listSuppliers` берутся из существующего `api/catalog.ts` (сигнатуры не меняются). `ApiError.status===409` — общий паттерн.

**Плейсхолдеры:** код полный. В тесте Task 2 закомментированные импорты/хелперы — на случай отсутствия в существующем `ImportPage.test.tsx`; исполнитель переиспользует имеющиеся или добавляет показанные (это инструкция, не TODO).
