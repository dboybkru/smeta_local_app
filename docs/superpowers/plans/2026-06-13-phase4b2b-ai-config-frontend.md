# Фаза 4b-2b — Админ-UI конфигурации AI (фронтенд) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать админу страницу `/admin/ai` для настройки слоя AI-провайдеров (провайдеры → модели → цели + советник) поверх готового бэкенда `/api/ai/*`.

**Architecture:** Одна страница `AiConfigPage` со state `version` (счётчик) и `bump()`; три самодостаточные секции-компонента (`ProvidersSection`/`ModelsSection`/`PurposesSection`), каждая грузит свои данные в `useEffect(..., [version])` и после любой мутации зовёт `onChanged()` → `bump()` → перезагрузка всех секций (так refresh моделей/добавление провайдера освежают зависимые селекты). Доступ — только admin (ссылка + бэкенд `require_admin`).

**Tech Stack:** React 19 + TS + Vite, react-router-dom v7, Tailwind v4; Vitest + @testing-library/react + userEvent. Деньги (цены моделей) — строки. Слой над `api()` из `api/client.ts`.

Рабочая папка: `D:\git\smeta_local_app\frontend`. Ветка: `phase-4b2b-ai-config` (уже создана, спек закоммичен). Команды: `npm run test [-- <file>]`, `npm run build`, `npm run lint` из `frontend`.

---

### Task 1: API-слой `api/ai.ts`

**Files:**
- Create: `frontend/src/api/ai.ts`

- [ ] **Step 1: Создать `frontend/src/api/ai.ts`**

```ts
import { api } from "./client";

export type AuthStyle = "bearer" | "x_api_key";

export type Provider = {
  id: number;
  name: string;
  base_url: string;
  auth_style: AuthStyle;
  enabled: boolean;
  has_key: boolean;
};

export type ProviderCreate = {
  name: string;
  base_url: string;
  auth_style: AuthStyle;
  api_key: string;
  enabled: boolean;
};

export type ProviderPatch = Partial<{
  base_url: string;
  auth_style: AuthStyle;
  api_key: string;
  enabled: boolean;
}>;

export type AiModel = {
  id: number;
  provider_id: number;
  model_id: string;
  label: string;
  input_price: string | null;
  output_price: string | null;
  strengths: string;
  enabled: boolean;
};

export type ModelPatch = Partial<{
  label: string;
  input_price: string | null;
  output_price: string | null;
  strengths: string;
  enabled: boolean;
}>;

export type Purpose = {
  id: number;
  key: string;
  title: string;
  description: string;
  primary_model_id: number | null;
  fallback_model_id: number | null;
  enabled: boolean;
};

export type PurposePatch = Partial<{
  title: string;
  description: string;
  primary_model_id: number | null;
  fallback_model_id: number | null;
  enabled: boolean;
}>;

export type Recommendation = {
  purpose_key: string;
  provider: string;
  model_id: string;
  rationale: string;
};

export function listProviders() {
  return api<Provider[]>("/ai/providers");
}
export function createProvider(body: ProviderCreate) {
  return api<Provider>("/ai/providers", { method: "POST", body: JSON.stringify(body) });
}
export function updateProvider(id: number, patch: ProviderPatch) {
  return api<Provider>(`/ai/providers/${id}`, { method: "PUT", body: JSON.stringify(patch) });
}
export function deleteProvider(id: number) {
  return api<void>(`/ai/providers/${id}`, { method: "DELETE" });
}
export function refreshModels(providerId: number) {
  return api<{ imported: number }>(`/ai/providers/${providerId}/models/refresh`, { method: "POST" });
}
export function listModels(providerId?: number) {
  const q = providerId != null ? `?provider_id=${providerId}` : "";
  return api<AiModel[]>(`/ai/models${q}`);
}
export function updateModel(id: number, patch: ModelPatch) {
  return api<AiModel>(`/ai/models/${id}`, { method: "PUT", body: JSON.stringify(patch) });
}
export function deleteModel(id: number) {
  return api<void>(`/ai/models/${id}`, { method: "DELETE" });
}
export function listPurposes() {
  return api<Purpose[]>("/ai/purposes");
}
export function updatePurpose(key: string, patch: PurposePatch) {
  return api<Purpose>(`/ai/purposes/${key}`, { method: "PUT", body: JSON.stringify(patch) });
}
export function recommend() {
  return api<Recommendation[]>("/ai/router/recommend", { method: "POST" });
}
export function testPurpose(key: string) {
  return api<{ ok: boolean; detail: string }>(`/ai/purposes/${key}/test`, { method: "POST" });
}
```

- [ ] **Step 2: Проверка типов** — Run: `npm run build`. Expected: PASS (модуль ни на что не ломает; пока не импортирован).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/ai.ts
git commit -m "feat(4b2b): AI config API layer"
```

---

### Task 2: ProvidersSection

**Files:**
- Create: `frontend/src/components/ai/ProvidersSection.tsx`
- Test: `frontend/src/components/ai/ProvidersSection.test.tsx`

- [ ] **Step 1: Написать падающий тест** `frontend/src/components/ai/ProvidersSection.test.tsx`

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProvidersSection from "./ProvidersSection";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const P = { id: 1, name: "VseGPT", base_url: "https://api.vsegpt.ru/v1", auth_style: "x_api_key", enabled: true, has_key: true };

describe("ProvidersSection", () => {
  it("lists providers with key status", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([P])));
    render(<ProvidersSection version={0} onChanged={() => {}} />);
    expect(await screen.findByText("VseGPT")).toBeInTheDocument();
    expect(screen.getByText("ключ задан")).toBeInTheDocument();
  });

  it("creates a provider (POST) and calls onChanged", async () => {
    const f = vi.fn(async (_url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") return json({ ...P, id: 2, name: "AITunnel" }, 201);
      return json([]);
    });
    vi.stubGlobal("fetch", f);
    const onChanged = vi.fn();
    render(<ProvidersSection version={0} onChanged={onChanged} />);
    await screen.findByText(/Провайдеров пока нет/);
    await userEvent.type(screen.getByPlaceholderText("Название"), "AITunnel");
    await userEvent.type(screen.getByPlaceholderText("https://api.vsegpt.ru/v1"), "https://api.aitunnel.ru/v1/");
    await userEvent.click(screen.getByText("Добавить"));
    expect(onChanged).toHaveBeenCalled();
    const posts = f.mock.calls.filter((c) => ((c[1] as RequestInit)?.method ?? "GET") === "POST");
    expect(posts.length).toBe(1);
  });

  it("imports models and shows count", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if (((init?.method ?? "GET") === "POST") && url.includes("/models/refresh")) return json({ imported: 5 });
      return json([P]);
    });
    vi.stubGlobal("fetch", f);
    render(<ProvidersSection version={0} onChanged={() => {}} />);
    await screen.findByText("VseGPT");
    await userEvent.click(screen.getByText("Импорт моделей"));
    expect(await screen.findByText(/Импортировано моделей: 5/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Запустить — упадёт** — Run: `npm run test -- src/components/ai/ProvidersSection.test.tsx`. Expected: FAIL (модуля нет).

- [ ] **Step 3: Реализовать** `frontend/src/components/ai/ProvidersSection.tsx`

```tsx
import { useEffect, useState } from "react";
import {
  createProvider, deleteProvider, listProviders, refreshModels, updateProvider,
  type AuthStyle, type Provider,
} from "../../api/ai";

type Props = { version: number; onChanged: () => void };

export default function ProvidersSection({ version, onChanged }: Props) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [authStyle, setAuthStyle] = useState<AuthStyle>("bearer");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    try {
      setProviders(await listProviders());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }
  useEffect(() => { void load(); }, [version]);

  async function add() {
    if (!name.trim() || !baseUrl.trim()) return;
    setError(""); setNotice("");
    try {
      await createProvider({
        name: name.trim(), base_url: baseUrl.trim(), auth_style: authStyle, api_key: apiKey, enabled: true,
      });
      setName(""); setBaseUrl(""); setApiKey(""); setAuthStyle("bearer");
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания");
    }
  }

  async function refresh(p: Provider) {
    setError(""); setNotice("");
    try {
      const r = await refreshModels(p.id);
      setNotice(`Импортировано моделей: ${r.imported}`);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка импорта");
    }
  }

  async function toggleEnabled(p: Provider) {
    setError("");
    try {
      await updateProvider(p.id, { enabled: !p.enabled });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка обновления");
    }
  }

  async function changeKey(p: Provider) {
    const key = window.prompt(`Новый ключ для «${p.name}» (пусто — отмена)`, "");
    if (!key) return;
    setError(""); setNotice("");
    try {
      await updateProvider(p.id, { api_key: key });
      setNotice("Ключ обновлён");
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка обновления ключа");
    }
  }

  async function remove(p: Provider) {
    if (!window.confirm(`Удалить провайдера «${p.name}»? Его модели тоже удалятся.`)) return;
    setError("");
    try {
      await deleteProvider(p.id);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    }
  }

  return (
    <section className="mb-10">
      <h2 className="mb-3 font-serif text-lg text-stone-900">Провайдеры</h2>
      {error && <p role="alert" className="mb-2 text-red-600">{error}</p>}
      {notice && <p className="mb-2 text-green-700">{notice}</p>}

      <div className="mb-2 flex flex-wrap items-end gap-2">
        <label className="text-sm text-stone-600"><span className="mb-1 block">Название</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Название"
            className="rounded border border-stone-300 px-2 py-1" />
        </label>
        <label className="text-sm text-stone-600"><span className="mb-1 block">Base URL</span>
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.vsegpt.ru/v1"
            className="w-64 rounded border border-stone-300 px-2 py-1" />
        </label>
        <label className="text-sm text-stone-600"><span className="mb-1 block">Авторизация</span>
          <select aria-label="Авторизация" value={authStyle} onChange={(e) => setAuthStyle(e.target.value as AuthStyle)}
            className="rounded border border-stone-300 px-2 py-1">
            <option value="bearer">Bearer</option>
            <option value="x_api_key">X-Api-Key</option>
          </select>
        </label>
        <label className="text-sm text-stone-600"><span className="mb-1 block">Ключ</span>
          <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="API-ключ"
            className="rounded border border-stone-300 px-2 py-1" />
        </label>
        <button onClick={() => void add()} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Добавить</button>
      </div>
      <p className="mb-4 text-xs text-stone-500">
        Примеры: AITunnel — https://api.aitunnel.ru/v1/ (Bearer); VseGPT — https://api.vsegpt.ru/v1 (X-Api-Key).
      </p>

      {providers.length === 0 ? (
        <p className="text-stone-500">Провайдеров пока нет — добавьте первого.</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead><tr className="border-b border-stone-300 text-left text-stone-500">
            <th className="py-2">Название</th><th>Base URL</th><th>Авторизация</th><th>Ключ</th><th>Вкл.</th><th /></tr></thead>
          <tbody>
            {providers.map((p) => (
              <tr key={p.id} className="border-b border-stone-200">
                <td className="py-2">{p.name}</td>
                <td className="text-stone-500">{p.base_url}</td>
                <td>{p.auth_style}</td>
                <td>{p.has_key ? "ключ задан" : "нет ключа"}</td>
                <td><input type="checkbox" aria-label={`Включён ${p.name}`} checked={p.enabled} onChange={() => void toggleEnabled(p)} /></td>
                <td className="space-x-2 text-right">
                  <button onClick={() => void refresh(p)} className="rounded border border-stone-500 px-2 py-1 text-stone-600">Импорт моделей</button>
                  <button onClick={() => void changeKey(p)} className="rounded border border-stone-500 px-2 py-1 text-stone-600">Ключ</button>
                  <button onClick={() => void remove(p)} className="rounded border border-red-700 px-2 py-1 text-red-700">Удалить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Запустить — пройдёт** — Run: `npm run test -- src/components/ai/ProvidersSection.test.tsx`. Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ai/ProvidersSection.tsx frontend/src/components/ai/ProvidersSection.test.tsx
git commit -m "feat(4b2b): providers section"
```

---

### Task 3: ModelsSection

**Files:**
- Create: `frontend/src/components/ai/ModelsSection.tsx`
- Test: `frontend/src/components/ai/ModelsSection.test.tsx`

- [ ] **Step 1: Написать падающий тест** `frontend/src/components/ai/ModelsSection.test.tsx`

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ModelsSection from "./ModelsSection";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const PROV = { id: 1, name: "VseGPT", base_url: "u", auth_style: "x_api_key", enabled: true, has_key: true };
const M = { id: 10, provider_id: 1, model_id: "gpt-4o", label: "GPT-4o", input_price: null, output_price: null, strengths: "", enabled: true };

function route(url: string) {
  if (url.includes("/ai/providers")) return json([PROV]);
  if (url.includes("/ai/models")) return json([M]);
  return json([]);
}

describe("ModelsSection", () => {
  it("renders models table", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => route(url)));
    render(<ModelsSection version={0} onChanged={() => {}} />);
    expect(await screen.findByText("gpt-4o")).toBeInTheDocument();
  });

  it("saves input price on blur (PUT)", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PUT") return json({ ...M, input_price: "10" });
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<ModelsSection version={0} onChanged={() => {}} />);
    const input = await screen.findByLabelText("Вход gpt-4o");
    await userEvent.type(input, "10");
    await userEvent.tab();
    const puts = f.mock.calls.filter((c) => (c[1] as RequestInit)?.method === "PUT");
    expect(puts.length).toBe(1);
    expect(JSON.parse((puts[0][1] as RequestInit).body as string)).toEqual({ input_price: "10" });
  });
});
```

- [ ] **Step 2: Запустить — упадёт** — Run: `npm run test -- src/components/ai/ModelsSection.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Реализовать** `frontend/src/components/ai/ModelsSection.tsx`

```tsx
import { useEffect, useState } from "react";
import {
  deleteModel, listModels, listProviders, updateModel,
  type AiModel, type ModelPatch, type Provider,
} from "../../api/ai";

type Props = { version: number; onChanged: () => void };

export default function ModelsSection({ version, onChanged }: Props) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<AiModel[]>([]);
  const [filter, setFilter] = useState<number | "">("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const [ps, ms] = await Promise.all([
        listProviders(),
        listModels(filter === "" ? undefined : filter),
      ]);
      setProviders(ps);
      setModels(ms);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }
  useEffect(() => { void load(); }, [version, filter]);

  function providerName(id: number) {
    return providers.find((p) => p.id === id)?.name ?? `#${id}`;
  }

  async function save(m: AiModel, patch: ModelPatch) {
    setError("");
    try {
      await updateModel(m.id, patch);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function remove(m: AiModel) {
    if (!window.confirm(`Удалить модель «${m.label}»?`)) return;
    setError("");
    try {
      await deleteModel(m.id);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    }
  }

  return (
    <section className="mb-10">
      <h2 className="mb-3 font-serif text-lg text-stone-900">Модели</h2>
      {error && <p role="alert" className="mb-2 text-red-600">{error}</p>}

      <label className="mb-4 block text-sm text-stone-600">
        <span className="mb-1 block">Провайдер</span>
        <select aria-label="Фильтр по провайдеру" value={filter}
          onChange={(e) => setFilter(e.target.value === "" ? "" : Number(e.target.value))}
          className="rounded border border-stone-300 px-2 py-1">
          <option value="">Все</option>
          {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </label>

      {models.length === 0 ? (
        <p className="text-stone-500">Моделей нет — добавьте провайдера и нажмите «Импорт моделей».</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead><tr className="border-b border-stone-300 text-left text-stone-500">
            <th className="py-2">Провайдер</th><th>ID модели</th><th>Название</th><th>Вход ₽/1M</th><th>Выход ₽/1M</th><th>Сильные стороны</th><th>Вкл.</th><th /></tr></thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.id} className="border-b border-stone-200 align-top">
                <td className="py-2 text-stone-500">{providerName(m.provider_id)}</td>
                <td className="font-mono text-xs">{m.model_id}</td>
                <td>
                  <input defaultValue={m.label} aria-label={`Название ${m.model_id}`}
                    onBlur={(e) => { if (e.target.value !== m.label) void save(m, { label: e.target.value }); }}
                    className="w-32 rounded border border-stone-300 px-1 py-0.5" />
                </td>
                <td>
                  <input defaultValue={m.input_price ?? ""} aria-label={`Вход ${m.model_id}`}
                    onBlur={(e) => { const v = e.target.value.trim() === "" ? null : e.target.value.trim(); if (v !== (m.input_price ?? null)) void save(m, { input_price: v }); }}
                    className="w-20 rounded border border-stone-300 px-1 py-0.5" />
                </td>
                <td>
                  <input defaultValue={m.output_price ?? ""} aria-label={`Выход ${m.model_id}`}
                    onBlur={(e) => { const v = e.target.value.trim() === "" ? null : e.target.value.trim(); if (v !== (m.output_price ?? null)) void save(m, { output_price: v }); }}
                    className="w-20 rounded border border-stone-300 px-1 py-0.5" />
                </td>
                <td>
                  <input defaultValue={m.strengths} aria-label={`Сильные стороны ${m.model_id}`}
                    onBlur={(e) => { if (e.target.value !== m.strengths) void save(m, { strengths: e.target.value }); }}
                    className="w-40 rounded border border-stone-300 px-1 py-0.5" />
                </td>
                <td><input type="checkbox" aria-label={`Включена ${m.model_id}`} checked={m.enabled} onChange={() => void save(m, { enabled: !m.enabled })} /></td>
                <td className="text-right">
                  <button onClick={() => void remove(m)} className="rounded border border-red-700 px-2 py-1 text-red-700">Удалить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Запустить — пройдёт** — Run: `npm run test -- src/components/ai/ModelsSection.test.tsx`. Expected: PASS (2/2).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ai/ModelsSection.tsx frontend/src/components/ai/ModelsSection.test.tsx
git commit -m "feat(4b2b): models section"
```

---

### Task 4: PurposesSection

**Files:**
- Create: `frontend/src/components/ai/PurposesSection.tsx`
- Test: `frontend/src/components/ai/PurposesSection.test.tsx`

- [ ] **Step 1: Написать падающий тест** `frontend/src/components/ai/PurposesSection.test.tsx`

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PurposesSection from "./PurposesSection";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const PROV = { id: 1, name: "VseGPT", base_url: "u", auth_style: "x_api_key", enabled: true, has_key: true };
const M = { id: 10, provider_id: 1, model_id: "gpt-4o", label: "GPT-4o", input_price: null, output_price: null, strengths: "", enabled: true };
const PURP = { id: 1, key: "proposal_generation", title: "Генерация КП", description: "", primary_model_id: null, fallback_model_id: null, enabled: true };

function route(url: string) {
  if (url.includes("/ai/purposes")) return json([PURP]);
  if (url.includes("/ai/models")) return json([M]);
  if (url.includes("/ai/providers")) return json([PROV]);
  return json([]);
}

describe("PurposesSection", () => {
  it("selects primary model (PUT)", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PUT") return json({ ...PURP, primary_model_id: 10 });
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<PurposesSection version={0} onChanged={() => {}} />);
    const select = await screen.findByLabelText("Основная модель proposal_generation");
    await userEvent.selectOptions(select, "10");
    const puts = f.mock.calls.filter((c) => (c[1] as RequestInit)?.method === "PUT");
    expect(JSON.parse((puts[0][1] as RequestInit).body as string)).toEqual({ primary_model_id: 10 });
  });

  it("recommends and applies", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes("/router/recommend")) return json([{ purpose_key: "proposal_generation", provider: "VseGPT", model_id: "gpt-4o", rationale: "хорошо пишет" }]);
      if ((init?.method ?? "GET") === "PUT") return json({ ...PURP, primary_model_id: 10 });
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<PurposesSection version={0} onChanged={() => {}} />);
    await screen.findByText("Генерация КП");
    await userEvent.click(screen.getByText("Подобрать"));
    expect(await screen.findByText(/хорошо пишет/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("Применить"));
    const puts = f.mock.calls.filter((c) => (c[1] as RequestInit)?.method === "PUT");
    expect(JSON.parse((puts[0][1] as RequestInit).body as string)).toEqual({ primary_model_id: 10 });
  });

  it("shows 503 hint when router not configured", async () => {
    const f = vi.fn(async (url: string) => {
      if (url.includes("/router/recommend")) return json({ detail: "router не настроен" }, 503);
      return route(url);
    });
    vi.stubGlobal("fetch", f);
    render(<PurposesSection version={0} onChanged={() => {}} />);
    await screen.findByText("Генерация КП");
    await userEvent.click(screen.getByText("Подобрать"));
    expect(await screen.findByText(/Советник недоступен/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Запустить — упадёт** — Run: `npm run test -- src/components/ai/PurposesSection.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Реализовать** `frontend/src/components/ai/PurposesSection.tsx`

```tsx
import { useEffect, useState } from "react";
import {
  listModels, listProviders, listPurposes, recommend, testPurpose, updatePurpose,
  type AiModel, type Provider, type Purpose, type Recommendation,
} from "../../api/ai";
import { ApiError } from "../../api/client";

type Props = { version: number; onChanged: () => void };

export default function PurposesSection({ version, onChanged }: Props) {
  const [purposes, setPurposes] = useState<Purpose[]>([]);
  const [models, setModels] = useState<AiModel[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [recs, setRecs] = useState<Record<string, Recommendation>>({});
  const [tests, setTests] = useState<Record<string, { ok: boolean; detail: string }>>({});
  const [error, setError] = useState("");

  async function load() {
    try {
      const [pp, ms, ps] = await Promise.all([listPurposes(), listModels(), listProviders()]);
      setPurposes(pp); setModels(ms); setProviders(ps);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }
  useEffect(() => { void load(); }, [version]);

  const enabledModels = models.filter((m) => m.enabled);
  function modelLabel(m: AiModel) {
    const prov = providers.find((p) => p.id === m.provider_id)?.name ?? `#${m.provider_id}`;
    return `${prov} / ${m.label}`;
  }

  async function setModel(p: Purpose, field: "primary_model_id" | "fallback_model_id", value: string) {
    const id = value === "" ? null : Number(value);
    setError("");
    try {
      await updatePurpose(p.key, { [field]: id });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function toggleEnabled(p: Purpose) {
    setError("");
    try {
      await updatePurpose(p.key, { enabled: !p.enabled });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function loadRecs() {
    setError("");
    try {
      const list = await recommend();
      const map: Record<string, Recommendation> = {};
      for (const r of list) map[r.purpose_key] = r;
      setRecs(map);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503)
        setError("Советник недоступен: цель «router» не настроена");
      else setError(err instanceof Error ? err.message : "Ошибка советника");
    }
  }

  async function applyRec(p: Purpose, rec: Recommendation) {
    const provId = providers.find((pr) => pr.name === rec.provider)?.id;
    const model = models.find((m) => m.model_id === rec.model_id && (provId == null || m.provider_id === provId));
    if (!model) { setError("Сначала импортируйте модели этого провайдера"); return; }
    await setModel(p, "primary_model_id", String(model.id));
  }

  async function runTest(p: Purpose) {
    setError("");
    try {
      setTests((cur) => ({ ...cur, [p.key]: await testPurpose(p.key) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка теста");
    }
  }

  return (
    <section>
      <h2 className="mb-3 font-serif text-lg text-stone-900">Цели</h2>
      {error && <p role="alert" className="mb-2 text-red-600">{error}</p>}

      <table className="w-full border-collapse text-sm">
        <thead><tr className="border-b border-stone-300 text-left text-stone-500">
          <th className="py-2">Цель</th><th>Основная модель</th><th>Резервная</th><th>Вкл.</th><th>Советник</th><th>Тест</th></tr></thead>
        <tbody>
          {purposes.map((p) => {
            const rec = recs[p.key];
            const t = tests[p.key];
            return (
              <tr key={p.key} className="border-b border-stone-200 align-top">
                <td className="py-2"><span className="block">{p.title}</span><span className="text-xs text-stone-400">{p.key}</span></td>
                <td>
                  <select aria-label={`Основная модель ${p.key}`} value={p.primary_model_id ?? ""}
                    onChange={(e) => void setModel(p, "primary_model_id", e.target.value)}
                    className="rounded border border-stone-300 px-1 py-0.5">
                    <option value="">— нет —</option>
                    {enabledModels.map((m) => <option key={m.id} value={m.id}>{modelLabel(m)}</option>)}
                  </select>
                </td>
                <td>
                  <select aria-label={`Резервная модель ${p.key}`} value={p.fallback_model_id ?? ""}
                    onChange={(e) => void setModel(p, "fallback_model_id", e.target.value)}
                    className="rounded border border-stone-300 px-1 py-0.5">
                    <option value="">— нет —</option>
                    {enabledModels.map((m) => <option key={m.id} value={m.id}>{modelLabel(m)}</option>)}
                  </select>
                </td>
                <td><input type="checkbox" aria-label={`Включена ${p.key}`} checked={p.enabled} onChange={() => void toggleEnabled(p)} /></td>
                <td>
                  <button onClick={() => void loadRecs()} className="rounded border border-stone-500 px-2 py-1 text-stone-600">Подобрать</button>
                  {rec && (
                    <div className="mt-1 text-xs text-stone-600">
                      <div>{rec.provider} / {rec.model_id}</div>
                      <div className="text-stone-400">{rec.rationale}</div>
                      <button onClick={() => void applyRec(p, rec)} className="mt-1 rounded border border-stone-700 px-2 py-0.5 text-stone-700">Применить</button>
                    </div>
                  )}
                </td>
                <td>
                  <button onClick={() => void runTest(p)} className="rounded border border-stone-500 px-2 py-1 text-stone-600">Тест</button>
                  {t && <span className={`ml-1 ${t.ok ? "text-green-700" : "text-red-600"}`}>{t.ok ? "✓" : `✗ ${t.detail}`}</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
```

- [ ] **Step 4: Запустить — пройдёт** — Run: `npm run test -- src/components/ai/PurposesSection.test.tsx`. Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ai/PurposesSection.tsx frontend/src/components/ai/PurposesSection.test.tsx
git commit -m "feat(4b2b): purposes section with advisor"
```

---

### Task 5: Страница + маршрут + ссылка в шапке

**Files:**
- Create: `frontend/src/pages/AiConfigPage.tsx`
- Modify: `frontend/src/App.tsx` (импорт + маршрут `/admin/ai`)
- Modify: `frontend/src/components/AppHeader.tsx` (ссылка «AI» для admin)
- Test: `frontend/src/components/AppHeader.test.tsx` (добавить проверки «AI»)

- [ ] **Step 1: Обновить тест шапки** — в `frontend/src/components/AppHeader.test.tsx`:
  - в тесте `"hides admin-only links from non-admins"` добавить строку:
    `expect(screen.queryByText("AI")).not.toBeInTheDocument();`
  - в тесте `"shows admin-only links to admins"` добавить строку:
    `expect(screen.getByText("AI")).toBeInTheDocument();`

- [ ] **Step 2: Запустить — упадёт** — Run: `npm run test -- src/components/AppHeader.test.tsx`. Expected: FAIL (ссылки «AI» ещё нет).

- [ ] **Step 3: Добавить ссылку в** `frontend/src/components/AppHeader.tsx` — сразу после блока ссылки «Поставщики» (`{isAdmin && (<Link to="/admin/suppliers" …>Поставщики</Link>)}`) вставить:

```tsx
        {isAdmin && (
          <Link to="/admin/ai" className="text-stone-600 hover:text-stone-900">AI</Link>
        )}
```

- [ ] **Step 4: Создать** `frontend/src/pages/AiConfigPage.tsx`

```tsx
import { useState } from "react";
import AppHeader from "../components/AppHeader";
import ProvidersSection from "../components/ai/ProvidersSection";
import ModelsSection from "../components/ai/ModelsSection";
import PurposesSection from "../components/ai/PurposesSection";

export default function AiConfigPage() {
  const [version, setVersion] = useState(0);
  const bump = () => setVersion((v) => v + 1);
  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8">
        <h1 className="mb-6 font-serif text-xl text-stone-900">Настройки AI</h1>
        <ProvidersSection version={version} onChanged={bump} />
        <ModelsSection version={version} onChanged={bump} />
        <PurposesSection version={version} onChanged={bump} />
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Подключить маршрут в** `frontend/src/App.tsx`
  - добавить импорт рядом с прочими страницами: `import AiConfigPage from "./pages/AiConfigPage";`
  - добавить маршрут сразу после строки `<Route path="/admin/suppliers" element={<SuppliersPage />} />`:
    `<Route path="/admin/ai" element={<AiConfigPage />} />`

- [ ] **Step 6: Запустить тест шапки — пройдёт** — Run: `npm run test -- src/components/AppHeader.test.tsx`. Expected: PASS.

- [ ] **Step 7: Полный прогон** — Run: `npm run test` (все зелёные), `npm run build` (чисто), `npm run lint` (0 errors; warnings `react-hooks/set-state-in-effect` допустимы).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/AiConfigPage.tsx frontend/src/App.tsx frontend/src/components/AppHeader.tsx frontend/src/components/AppHeader.test.tsx
git commit -m "feat(4b2b): AI config page, route and header link"
```

---

## Самопроверка плана

**Покрытие спека:** провайдеры (CRUD+refresh) — Task 2 ✅; модели (список/правка/удаление/фильтр) — Task 3 ✅; цели (primary/fallback/enabled) + советник (кнопка/применить/503) + тест — Task 4 ✅; страница `/admin/ai` одной страницей с 3 секциями + ссылка admin — Task 5 ✅; API-слой — Task 1 ✅.

**Плейсхолдеры:** нет — весь код приведён целиком.

**Согласованность типов:** `Provider/AiModel/Purpose/Recommendation/*Patch` определены в Task 1 и используются в Task 2–4 теми же именами; пропсы секций `{version:number; onChanged:()=>void}` единообразны; `recommend()` возвращает `Recommendation[]`, раскладывается в `Record<key,Recommendation>`; применение мапит `provider`(имя)+`model_id`(строка) → `AiModel.id`. Деньги — строки/`null`.
