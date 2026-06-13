# Фаза 4b-1 — Фронтенд КП-потока Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** UI для бэкенда фазы 4a: страница профиля исполнителя, вкладки «КП»/«Поделиться» в редакторе сметы (блоки КП + AI-генерация, экспорт Excel/PDF, публичные ссылки).

**Architecture:** Вкладки (локальный стейт) в `EstimateEditorPage`: существующая таблица 3b → вкладка «Смета», новые «КП» и «Поделиться». Отдельная страница `/profile`. Тонкие API-модули над `api()`/`getTokens` из `src/api/client.ts`. Бэкенд-правка: добавить `proposal` в `EstimateDetail`, чтобы фронт получал блоки.

**Tech Stack:** React 19 + TypeScript + Vite + Tailwind v4 + react-router-dom v7; Vitest + @testing-library/react (+ userEvent). Бэкенд: FastAPI/Pydantic.

---

## Соглашения (фаза 3b)

- API: `import { api } from "../api/client"` ; деньги/qty — строки. Бинарь (экспорт) — отдельным `fetch` с `getTokens()` (не `api()`, т.к. нужен Blob).
- Доступ: `canEdit = user?.role === "estimator" || user?.role === "admin"`.
- Тесты (Vitest): паттерн из `EstimatesListPage.test.tsx` — `json()`-хелпер, `vi.stubGlobal("fetch", router(...))`, `vi.spyOn(authModule,"useAuth").mockReturnValue({user, loginWithPassword, acceptTokens, logout})`, рендер в `<MemoryRouter><AuthProvider>…`. `afterEach(cleanup; vi.restoreAllMocks)`.
- Запуск фронт-тестов: из `frontend/` → `npm run test -- <file>`; сборка `npm run build`; линт `npm run lint`.
- Бэкенд-тест (Task 1): из `backend/` → `python -m pytest …`.

## File Structure

| Файл | Ответственность |
|---|---|
| `backend/app/estimates/schemas.py` | + `proposal` в `EstimateDetail` |
| `frontend/src/api/proposals.ts` | `ProposalBlocks` тип, `generateProposal`, `patchProposal` |
| `frontend/src/api/profile.ts` | `Profile`/`ProfileIn`, `getProfile`, `putProfile` |
| `frontend/src/api/publicLinks.ts` | `PublicLink`, `listLinks`, `createLink`, `revokeLink` |
| `frontend/src/api/export.ts` | `downloadExport(id, fmt, level)` (Blob) |
| `frontend/src/api/estimates.ts` | + `proposal` в `EstimateDetail` |
| `frontend/src/pages/ProfilePage.tsx` | форма реквизитов `/profile` |
| `frontend/src/components/estimate/EstimateTabs.tsx` | переключатель Смета/КП/Поделиться |
| `frontend/src/components/estimate/ProposalBlocksEditor.tsx` | 7 блоков, advantages-список |
| `frontend/src/components/estimate/ProposalTab.tsx` | AI-кнопка + плашка 503 + editor |
| `frontend/src/components/estimate/ExportButtons.tsx` | уровень + Excel/PDF |
| `frontend/src/components/estimate/PublicLinksManager.tsx` | создать/список/отозвать |
| `frontend/src/components/estimate/ShareTab.tsx` | компоновка Export+Links |
| `frontend/src/pages/EstimateEditorPage.tsx` | интеграция вкладок |
| `frontend/src/components/AppHeader.tsx` | + ссылка «Реквизиты» |
| `frontend/src/App.tsx` | + маршрут `/profile` |

---

## Task 1: Бэкенд — отдать `proposal` в детальной смете

**Files:**
- Modify: `backend/app/estimates/schemas.py`
- Test: `backend/tests/test_estimate_detail.py` (добавить тест)

- [ ] **Step 1: Failing test** — добавить в `backend/tests/test_estimate_detail.py`:
```python
def test_detail_includes_proposal(client, db_session):
    from app.auth.models import User
    from app.core.security import create_access_token
    from app.estimates.models import Estimate

    u = User(email="p@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Объект",
                   proposal={"title": "КП", "advantages": ["a"]})
    db_session.add(est); db_session.commit(); db_session.refresh(est)
    hdr = {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}
    r = client.get(f"/api/estimates/{est.id}", headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["proposal"] == {"title": "КП", "advantages": ["a"]}


def test_detail_proposal_null_by_default(client, db_session):
    from app.auth.models import User
    from app.core.security import create_access_token
    from app.estimates.models import Estimate

    u = User(email="p2@x.ru", name="U", role="estimator", status="active")
    db_session.add(u); db_session.commit()
    est = Estimate(owner_id=u.id, object_name="Объект")
    db_session.add(est); db_session.commit(); db_session.refresh(est)
    hdr = {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}
    r = client.get(f"/api/estimates/{est.id}", headers=hdr)
    assert r.json()["proposal"] is None
```

- [ ] **Step 2: Run, confirm FAIL** — `python -m pytest tests/test_estimate_detail.py -k proposal -v` (KeyError/`proposal` отсутствует)

- [ ] **Step 3: Add field** — в `backend/app/estimates/schemas.py`, в классе `EstimateDetail` (после `totals: EstimateTotals | None = None`) добавить:
```python
    proposal: dict | None = None
```
(Эндпоинт `get_estimate` делает `EstimateDetail.model_validate(est)` — поле `est.proposal` подхватится автоматически. proposal не содержит маржи/закупки → виден всем, кто видит смету.)

- [ ] **Step 4: Run, confirm PASS** — `python -m pytest tests/test_estimate_detail.py -v`

- [ ] **Step 5: Commit**
```bash
git add backend/app/estimates/schemas.py backend/tests/test_estimate_detail.py
git commit -m "feat(estimates): expose proposal blocks in EstimateDetail"
```

---

## Task 2: API-модули фронтенда (proposals, profile, publicLinks, export) + тип proposal

**Files:**
- Create: `frontend/src/api/proposals.ts`
- Create: `frontend/src/api/profile.ts`
- Create: `frontend/src/api/publicLinks.ts`
- Create: `frontend/src/api/export.ts`
- Modify: `frontend/src/api/estimates.ts`
- Test: `frontend/src/api/proposals.test.ts`

- [ ] **Step 1: Failing test** — `frontend/src/api/proposals.test.ts`:
```ts
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
  expect(f.mock.calls[0][0]).toBe("/api/estimates/5/proposal/generate");
  expect((f.mock.calls[0][1] as RequestInit).method).toBe("POST");
});

it("patchProposal PATCHes partial blocks", async () => {
  const f = vi.fn(async () => json({ title: "New", subtitle: "", pain: "", solution: "", advantages: [], terms: "", cta: "" }));
  vi.stubGlobal("fetch", f);
  const out = await patchProposal(5, { title: "New" });
  expect(out.title).toBe("New");
  expect((f.mock.calls[0][1] as RequestInit).method).toBe("PATCH");
  expect((f.mock.calls[0][1] as RequestInit).body).toBe(JSON.stringify({ title: "New" }));
});
```

- [ ] **Step 2: Run, confirm FAIL** — `npm run test -- src/api/proposals.test.ts`

- [ ] **Step 3: Create `frontend/src/api/proposals.ts`:**
```ts
import { api } from "./client";

export type ProposalBlocks = {
  title: string;
  subtitle: string;
  pain: string;
  solution: string;
  advantages: string[];
  terms: string;
  cta: string;
};

export type ProposalPatch = Partial<ProposalBlocks>;

const j = (b: unknown) => JSON.stringify(b);

export const generateProposal = (estimateId: number) =>
  api<ProposalBlocks>(`/estimates/${estimateId}/proposal/generate`, { method: "POST" });

export const patchProposal = (estimateId: number, patch: ProposalPatch) =>
  api<ProposalBlocks>(`/estimates/${estimateId}/proposal`, { method: "PATCH", body: j(patch) });
```

- [ ] **Step 4: Create `frontend/src/api/profile.ts`:**
```ts
import { api } from "./client";

export type Contacts = { phone: string; email: string; address: string; site: string };

export type Profile = {
  id: number;
  org_name: string;
  inn: string;
  contacts: Contacts;
  bank_requisites: string;
  utp: string[];
  cases: string[];
  guarantee: string;
  logo_url: string;
  updated_at: string;
};

export type ProfileIn = Omit<Profile, "id" | "updated_at">;

const j = (b: unknown) => JSON.stringify(b);

export const getProfile = () => api<Profile>("/profile");
export const putProfile = (body: ProfileIn) => api<Profile>("/profile", { method: "PUT", body: j(body) });
```

- [ ] **Step 5: Create `frontend/src/api/publicLinks.ts`:**
```ts
import { api } from "./client";

export type PublicLink = {
  id: number;
  estimate_id: number;
  token: string;
  level: string;
  expires_at: string | null;
  watermark_enabled: boolean;
  watermark_text: string;
  revoked: boolean;
  created_at: string;
};

export type PublicLinkCreate = {
  level: string;
  expires_at?: string | null;
  watermark_enabled?: boolean;
  watermark_text?: string;
};

const j = (b: unknown) => JSON.stringify(b);

export const listLinks = (estimateId: number) =>
  api<PublicLink[]>(`/estimates/${estimateId}/public-links`);
export const createLink = (estimateId: number, body: PublicLinkCreate) =>
  api<PublicLink>(`/estimates/${estimateId}/public-links`, { method: "POST", body: j(body) });
export const revokeLink = (linkId: number) =>
  api<void>(`/public-links/${linkId}`, { method: "DELETE" });
```

- [ ] **Step 6: Create `frontend/src/api/export.ts`:**
```ts
import { ApiError, getTokens } from "./client";

export type ExportFormat = "xlsx" | "pdf";
export type ExportLevel = "full" | "cover" | "estimate";

// Бинарное скачивание: нужен заголовок Authorization, поэтому не api() (тот делает .json()).
export async function downloadExport(
  estimateId: number,
  fmt: ExportFormat,
  level: ExportLevel,
): Promise<void> {
  const { access } = getTokens();
  const resp = await fetch(`/api/estimates/${estimateId}/export.${fmt}?level=${level}`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  });
  if (!resp.ok) throw new ApiError(resp.status, resp.statusText);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `estimate-${estimateId}.${fmt}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 7: Add proposal type to estimates** — в `frontend/src/api/estimates.ts`: вверху добавить `import type { ProposalBlocks } from "./proposals";`, и в типе `EstimateDetail` добавить поле:
```ts
export type EstimateDetail = Omit<Estimate, "branches"> & {
  branches: BranchDetail[];
  totals: EstimateTotals;
  proposal: ProposalBlocks | null;
};
```

- [ ] **Step 8: Run, confirm PASS** — `npm run test -- src/api/proposals.test.ts` (2 passed)

- [ ] **Step 9: Commit**
```bash
git add frontend/src/api/proposals.ts frontend/src/api/profile.ts frontend/src/api/publicLinks.ts frontend/src/api/export.ts frontend/src/api/estimates.ts frontend/src/api/proposals.test.ts
git commit -m "feat(4b1): api modules (proposals/profile/publicLinks/export) + EstimateDetail.proposal"
```

---

## Task 3: Страница профиля `/profile` + маршрут + ссылка в шапке

**Files:**
- Create: `frontend/src/pages/ProfilePage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/AppHeader.tsx`
- Test: `frontend/src/pages/ProfilePage.test.tsx`

- [ ] **Step 1: Failing test** — `frontend/src/pages/ProfilePage.test.tsx`:
```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import * as authModule from "../auth/AuthContext";
import ProfilePage from "./ProfilePage";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
const EMPTY = { id: 0, org_name: "", inn: "", contacts: { phone: "", email: "", address: "", site: "" },
  bank_requisites: "", utp: [], cases: [], guarantee: "", logo_url: "", updated_at: "1970-01-01T00:00:00Z" };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function stub() {
  vi.spyOn(authModule, "useAuth").mockReturnValue({
    user: { id: 1, email: "a@b.c", name: "A", role: "estimator", status: "active" },
    loginWithPassword: vi.fn(), acceptTokens: vi.fn(), logout: vi.fn(),
  });
}
function renderPage() {
  return render(<MemoryRouter><AuthProvider><ProfilePage /></AuthProvider></MemoryRouter>);
}

describe("ProfilePage", () => {
  it("loads empty profile then saves via PUT", async () => {
    const f = vi.fn(async (_url: string, init?: RequestInit) =>
      (init?.method ?? "GET") === "PUT" ? json({ ...EMPTY, org_name: "ООО Ромашка" }) : json(EMPTY));
    vi.stubGlobal("fetch", f); stub(); renderPage();
    const org = await screen.findByLabelText("Организация");
    await userEvent.type(org, "ООО Ромашка");
    await userEvent.click(screen.getByText("Сохранить"));
    const put = f.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "PUT");
    expect(put).toBeTruthy();
    expect((put![1] as RequestInit).body).toContain("ООО Ромашка");
  });

  it("adds and removes a УТП item", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(EMPTY))); stub(); renderPage();
    await screen.findByLabelText("Организация");
    await userEvent.type(screen.getByPlaceholderText("Новое УТП"), "Гарантия 5 лет");
    await userEvent.click(screen.getByText("+ УТП"));
    expect(screen.getByText("Гарантия 5 лет")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Удалить УТП Гарантия 5 лет"));
    expect(screen.queryByText("Гарантия 5 лет")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run, confirm FAIL** — `npm run test -- src/pages/ProfilePage.test.tsx`

- [ ] **Step 3: Create `frontend/src/pages/ProfilePage.tsx`:**
```tsx
import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import { getProfile, putProfile, type Contacts, type ProfileIn } from "../api/profile";

const EMPTY_IN: ProfileIn = {
  org_name: "", inn: "",
  contacts: { phone: "", email: "", address: "", site: "" },
  bank_requisites: "", utp: [], cases: [], guarantee: "", logo_url: "",
};

export default function ProfilePage() {
  const [form, setForm] = useState<ProfileIn>(EMPTY_IN);
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getProfile()
      .then((p) =>
        setForm({
          org_name: p.org_name, inn: p.inn, contacts: p.contacts,
          bank_requisites: p.bank_requisites, utp: p.utp, cases: p.cases,
          guarantee: p.guarantee, logo_url: p.logo_url,
        }),
      )
      .catch((e) => setError(e instanceof Error ? e.message : "Ошибка загрузки"))
      .finally(() => setLoading(false));
  }, []);

  function set<K extends keyof ProfileIn>(k: K, v: ProfileIn[K]) {
    setForm((f) => ({ ...f, [k]: v }));
    setSaved(false);
  }
  function setContact<K extends keyof Contacts>(k: K, v: string) {
    setForm((f) => ({ ...f, contacts: { ...f.contacts, [k]: v } }));
    setSaved(false);
  }

  async function save() {
    setError("");
    try {
      await putProfile(form);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    }
  }

  if (loading) return <Shell><p className="text-stone-500">Загрузка…</p></Shell>;

  return (
    <Shell>
      <h1 className="mb-4 font-serif text-2xl text-stone-900">Реквизиты исполнителя</h1>
      {error && <p role="alert" className="mb-3 text-red-600">{error}</p>}
      <div className="grid max-w-2xl gap-4">
        <Field label="Организация" value={form.org_name} onChange={(v) => set("org_name", v)} />
        <Field label="ИНН" value={form.inn} onChange={(v) => set("inn", v)} />
        <Field label="Телефон" value={form.contacts.phone} onChange={(v) => setContact("phone", v)} />
        <Field label="Email" value={form.contacts.email} onChange={(v) => setContact("email", v)} />
        <Field label="Адрес" value={form.contacts.address} onChange={(v) => setContact("address", v)} />
        <Field label="Сайт" value={form.contacts.site} onChange={(v) => setContact("site", v)} />
        <Area label="Банковские реквизиты" value={form.bank_requisites} onChange={(v) => set("bank_requisites", v)} />
        <Area label="Гарантия" value={form.guarantee} onChange={(v) => set("guarantee", v)} />
        <Field label="Логотип (URL)" value={form.logo_url} onChange={(v) => set("logo_url", v)} />
        <ListField label="УТП" items={form.utp} onChange={(v) => set("utp", v)} />
        <ListField label="Кейсы" items={form.cases} onChange={(v) => set("cases", v)} />
        <div className="flex items-center gap-3">
          <button onClick={save} className="rounded border border-stone-700 px-4 py-1.5 text-stone-700">Сохранить</button>
          {saved && <span className="text-green-700 text-sm">Сохранено</span>}
        </div>
      </div>
    </Shell>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="text-stone-500">{label}</span>
      <input aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded border border-stone-300 px-2 py-1" />
    </label>
  );
}
function Area({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="text-stone-500">{label}</span>
      <textarea aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded border border-stone-300 px-2 py-1" rows={3} />
    </label>
  );
}
function ListField({ label, items, onChange }: { label: string; items: string[]; onChange: (v: string[]) => void }) {
  const [draft, setDraft] = useState("");
  return (
    <div className="grid gap-1 text-sm">
      <span className="text-stone-500">{label}</span>
      <div className="flex flex-wrap gap-2">
        {items.map((it, i) => (
          <span key={i} className="flex items-center gap-1 rounded-full bg-stone-200 px-3 py-0.5">
            {it}
            <button aria-label={`Удалить ${label} ${it}`} onClick={() => onChange(items.filter((_, j) => j !== i))}>✕</button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={`Новое ${label}`}
          className="rounded border border-stone-300 px-2 py-1" />
        <button onClick={() => { if (draft.trim()) { onChange([...items, draft.trim()]); setDraft(""); } }}
          className="rounded border border-stone-700 px-3 py-1 text-stone-700">+ {label}</button>
      </div>
    </div>
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

- [ ] **Step 4: Route** — в `frontend/src/App.tsx`: добавить `import ProfilePage from "./pages/ProfilePage";` и внутри `<RequireAuth>`-блока `<Route path="/profile" element={<ProfilePage />} />`.

- [ ] **Step 5: Header link** — в `frontend/src/components/AppHeader.tsx` после ссылки «Сметы» добавить (видна всем авторизованным estimator/admin; viewer тоже видит, но бэк не даст писать — приемлемо, профиль это его собственные реквизиты только у estimator/admin; для простоты показываем всем):
```tsx
        <Link to="/estimates" className="text-stone-600 hover:text-stone-900">Сметы</Link>
        <Link to="/profile" className="text-stone-600 hover:text-stone-900">Реквизиты</Link>
```

- [ ] **Step 6: Run, confirm PASS** — `npm run test -- src/pages/ProfilePage.test.tsx` (2 passed)

- [ ] **Step 7: Commit**
```bash
git add frontend/src/pages/ProfilePage.tsx frontend/src/App.tsx frontend/src/components/AppHeader.tsx frontend/src/pages/ProfilePage.test.tsx
git commit -m "feat(4b1): profile page (/profile) + header link + route"
```

---

## Task 4: Переключатель вкладок в редакторе сметы

**Files:**
- Create: `frontend/src/components/estimate/EstimateTabs.tsx`
- Modify: `frontend/src/pages/EstimateEditorPage.tsx`
- Test: `frontend/src/components/estimate/EstimateTabs.test.tsx`

- [ ] **Step 1: Failing test** — `frontend/src/components/estimate/EstimateTabs.test.tsx`:
```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EstimateTabs from "./EstimateTabs";

afterEach(cleanup);

describe("EstimateTabs", () => {
  it("shows active tab content and switches", async () => {
    render(
      <EstimateTabs
        smeta={<div>SMETA</div>}
        kp={<div>KP</div>}
        share={<div>SHARE</div>}
      />,
    );
    expect(screen.getByText("SMETA")).toBeInTheDocument();
    expect(screen.queryByText("KP")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "КП" }));
    expect(screen.getByText("KP")).toBeInTheDocument();
    expect(screen.queryByText("SMETA")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Поделиться" }));
    expect(screen.getByText("SHARE")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run, confirm FAIL** — `npm run test -- src/components/estimate/EstimateTabs.test.tsx`

- [ ] **Step 3: Create `frontend/src/components/estimate/EstimateTabs.tsx`:**
```tsx
import { useState } from "react";

type Tab = "smeta" | "kp" | "share";
const LABELS: Record<Tab, string> = { smeta: "Смета", kp: "КП", share: "Поделиться" };

export default function EstimateTabs({
  smeta, kp, share,
}: {
  smeta: React.ReactNode;
  kp: React.ReactNode;
  share: React.ReactNode;
}) {
  const [tab, setTab] = useState<Tab>("smeta");
  const content: Record<Tab, React.ReactNode> = { smeta, kp, share };
  return (
    <div>
      <div role="tablist" className="mb-4 flex gap-1 border-b border-stone-200">
        {(Object.keys(LABELS) as Tab[]).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={
              "px-4 py-2 text-sm -mb-px border-b-2 " +
              (tab === t ? "border-stone-800 text-stone-900" : "border-transparent text-stone-500 hover:text-stone-800")
            }
          >
            {LABELS[t]}
          </button>
        ))}
      </div>
      <div>{content[tab]}</div>
    </div>
  );
}
```

- [ ] **Step 4: Integrate into `EstimateEditorPage.tsx`** — обернуть текущее содержимое (таблица разделов + добавление раздела + `EstimateTotalsBar`) во вкладку «Смета», добавить «КП» и «Поделиться». Заменить блок `return (<Shell>…</Shell>)` на:
```tsx
  const smetaTab = (
    <>
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
    </>
  );

  return (
    <Shell>
      {e.error && <p role="alert" className="mb-3 text-red-600">{e.error}</p>}
      <EstimateHeader key={est.id} estimate={est} clients={clients} canEdit={e.canEdit} onPatch={e.patchEstimate} onCreateClient={handleCreateClient} />
      <EstimateTabs
        smeta={smetaTab}
        kp={<ProposalTab estimateId={est.id} initial={est.proposal} canEdit={e.canEdit} />}
        share={<ShareTab estimateId={est.id} canEdit={e.canEdit} />}
      />
    </Shell>
  );
```
Добавить импорты вверху: `import EstimateTabs from "../components/estimate/EstimateTabs";`, `import ProposalTab from "../components/estimate/ProposalTab";`, `import ShareTab from "../components/estimate/ShareTab";`.
> Файлы `ProposalTab`/`ShareTab` создаются в Task 5–8 — до их создания этот шаг не скомпилируется. **Порядок:** сделать Task 5 (ProposalTab + ProposalBlocksEditor) и Task 6–8 (ShareTab и его части), затем выполнить этот Step. Если исполняешь по порядку — временно закомментируй строки `kp=`/`share=` (поставь заглушки `<div/>`), доведи Task 4 до зелёного теста EstimateTabs, и раскомментируй в Task 8. Реальная интеграция и общий прогон — в Task 8.

- [ ] **Step 5: Run, confirm PASS** — `npm run test -- src/components/estimate/EstimateTabs.test.tsx`

- [ ] **Step 6: Commit**
```bash
git add frontend/src/components/estimate/EstimateTabs.tsx frontend/src/components/estimate/EstimateTabs.test.tsx
git commit -m "feat(4b1): estimate tabs (Смета/КП/Поделиться)"
```

---

## Task 5: Редактор блоков КП + вкладка КП (AI-генерация)

**Files:**
- Create: `frontend/src/components/estimate/ProposalBlocksEditor.tsx`
- Create: `frontend/src/components/estimate/ProposalTab.tsx`
- Test: `frontend/src/components/estimate/ProposalTab.test.tsx`

- [ ] **Step 1: Failing test** — `frontend/src/components/estimate/ProposalTab.test.tsx`:
```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProposalTab from "./ProposalTab";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
const BLOCKS = { title: "Ремонт под ключ", subtitle: "", pain: "", solution: "", advantages: ["Свои бригады"], terms: "", cta: "" };
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("ProposalTab", () => {
  it("generates blocks via AI and shows them", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.stubGlobal("fetch", vi.fn(async () => json(BLOCKS)));
    render(<ProposalTab estimateId={5} initial={null} canEdit={true} />);
    await userEvent.click(screen.getByText("✨ Сгенерировать AI"));
    expect(await screen.findByDisplayValue("Ремонт под ключ")).toBeInTheDocument();
    expect(screen.getByText("Свои бригады")).toBeInTheDocument();
  });

  it("shows 'AI not configured' banner on 503", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "AI не настроен" }, 503)));
    render(<ProposalTab estimateId={5} initial={null} canEdit={true} />);
    await userEvent.click(screen.getByText("✨ Сгенерировать AI"));
    expect(await screen.findByText(/AI не настроен/)).toBeInTheDocument();
  });

  it("read-only for viewer (no AI button, inputs disabled)", () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(BLOCKS)));
    render(<ProposalTab estimateId={5} initial={BLOCKS} canEdit={false} />);
    expect(screen.queryByText("✨ Сгенерировать AI")).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("Ремонт под ключ")).toBeDisabled();
  });

  it("patches a field on blur", async () => {
    const f = vi.fn(async () => json({ ...BLOCKS, title: "Новый" }));
    vi.stubGlobal("fetch", f);
    render(<ProposalTab estimateId={5} initial={BLOCKS} canEdit={true} />);
    const title = screen.getByDisplayValue("Ремонт под ключ");
    await userEvent.clear(title);
    await userEvent.type(title, "Новый");
    title.blur();
    await vi.waitFor(() => {
      const patched = f.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "PATCH");
      expect(patched).toBeTruthy();
    });
  });
});
```

- [ ] **Step 2: Run, confirm FAIL** — `npm run test -- src/components/estimate/ProposalTab.test.tsx`

- [ ] **Step 3: Create `frontend/src/components/estimate/ProposalBlocksEditor.tsx`:**
```tsx
import { useState } from "react";
import type { ProposalBlocks } from "../../api/proposals";

type Props = {
  blocks: ProposalBlocks;
  canEdit: boolean;
  onField: (key: keyof ProposalBlocks, value: string) => void;       // text fields, on blur
  onAdvantages: (items: string[]) => void;                            // list, immediate
};

const TEXT_FIELDS: { key: keyof ProposalBlocks; label: string; area?: boolean }[] = [
  { key: "title", label: "Заголовок" },
  { key: "subtitle", label: "Подзаголовок" },
  { key: "pain", label: "Боль клиента", area: true },
  { key: "solution", label: "Решение / результат", area: true },
  { key: "terms", label: "Условия", area: true },
  { key: "cta", label: "Призыв к действию" },
];

export default function ProposalBlocksEditor({ blocks, canEdit, onField, onAdvantages }: Props) {
  return (
    <div className="grid max-w-2xl gap-4">
      {TEXT_FIELDS.map(({ key, label, area }) => (
        <label key={key} className="grid gap-1 text-sm">
          <span className="text-stone-500">{label}</span>
          {area ? (
            <textarea
              aria-label={label}
              defaultValue={blocks[key] as string}
              disabled={!canEdit}
              rows={3}
              onBlur={(e) => onField(key, e.target.value)}
              className="rounded border border-stone-300 px-2 py-1 disabled:bg-stone-100"
            />
          ) : (
            <input
              aria-label={label}
              defaultValue={blocks[key] as string}
              disabled={!canEdit}
              onBlur={(e) => onField(key, e.target.value)}
              className="rounded border border-stone-300 px-2 py-1 disabled:bg-stone-100"
            />
          )}
        </label>
      ))}
      <AdvantagesEditor items={blocks.advantages} canEdit={canEdit} onChange={onAdvantages} />
    </div>
  );
}

function AdvantagesEditor({ items, canEdit, onChange }: { items: string[]; canEdit: boolean; onChange: (v: string[]) => void }) {
  return (
    <div className="grid gap-1 text-sm">
      <span className="text-stone-500">Преимущества</span>
      <div className="flex flex-wrap gap-2">
        {items.map((it, i) => (
          <span key={i} className="flex items-center gap-1 rounded-full bg-stone-200 px-3 py-0.5">
            {it}
            {canEdit && (
              <button aria-label={`Удалить преимущество ${it}`} onClick={() => onChange(items.filter((_, j) => j !== i))}>✕</button>
            )}
          </span>
        ))}
      </div>
      {canEdit && <AddAdvantage onAdd={(v) => onChange([...items, v])} />}
    </div>
  );
}

function AddAdvantage({ onAdd }: { onAdd: (v: string) => void }) {
  const [draft, setDraft] = useState("");
  return (
    <div className="flex gap-2">
      <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Новое преимущество"
        className="rounded border border-stone-300 px-2 py-1" />
      <button onClick={() => { if (draft.trim()) { onAdd(draft.trim()); setDraft(""); } }}
        className="rounded border border-stone-700 px-3 py-1 text-stone-700">+ преимущество</button>
    </div>
  );
}
```

- [ ] **Step 4: Create `frontend/src/components/estimate/ProposalTab.tsx`:**
```tsx
import { useState } from "react";
import { ApiError } from "../../api/client";
import { generateProposal, patchProposal, type ProposalBlocks } from "../../api/proposals";
import ProposalBlocksEditor from "./ProposalBlocksEditor";

const EMPTY: ProposalBlocks = { title: "", subtitle: "", pain: "", solution: "", advantages: [], terms: "", cta: "" };

export default function ProposalTab({
  estimateId, initial, canEdit,
}: {
  estimateId: number;
  initial: ProposalBlocks | null;
  canEdit: boolean;
}) {
  const [blocks, setBlocks] = useState<ProposalBlocks>(initial ?? EMPTY);
  const [hasBlocks, setHasBlocks] = useState<boolean>(initial != null);
  const [busy, setBusy] = useState(false);
  const [notConfigured, setNotConfigured] = useState(false);
  const [error, setError] = useState("");

  async function generate() {
    if (hasBlocks && !window.confirm("Перезаписать существующие блоки КП?")) return;
    setBusy(true); setError(""); setNotConfigured(false);
    try {
      const out = await generateProposal(estimateId);
      setBlocks(out); setHasBlocks(true);
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) setNotConfigured(true);
      else setError(e instanceof Error ? e.message : "Ошибка генерации");
    } finally {
      setBusy(false);
    }
  }

  async function saveField(key: keyof ProposalBlocks, value: string) {
    if ((blocks[key] as string) === value) return;
    try {
      const out = await patchProposal(estimateId, { [key]: value });
      setBlocks(out); setHasBlocks(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    }
  }

  async function saveAdvantages(items: string[]) {
    setBlocks((b) => ({ ...b, advantages: items }));
    try {
      const out = await patchProposal(estimateId, { advantages: items });
      setBlocks(out); setHasBlocks(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    }
  }

  return (
    <div>
      {notConfigured && (
        <div className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          ⚠ AI не настроен — заполните блоки вручную или попросите администратора подключить провайдера.
        </div>
      )}
      {error && <p role="alert" className="mb-3 text-red-600 text-sm">{error}</p>}
      {canEdit && (
        <div className="mb-4 flex items-center gap-3">
          <button onClick={generate} disabled={busy}
            className="rounded border border-stone-700 px-4 py-1.5 text-stone-700 disabled:opacity-50">
            {busy ? "Генерация…" : "✨ Сгенерировать AI"}
          </button>
          <span className="text-xs text-stone-400">перезапишет все блоки · сохраняется автоматически</span>
        </div>
      )}
      <ProposalBlocksEditor blocks={blocks} canEdit={canEdit} onField={saveField} onAdvantages={saveAdvantages} />
    </div>
  );
}
```
> `ProposalBlocksEditor` использует `defaultValue` (uncontrolled) — поэтому после `generate()` поля надо перерисовать с новыми значениями. Чтобы uncontrolled-инпуты обновились, добавь `key` на редактор, завязанный на факт генерации: замени `<ProposalBlocksEditor … />` на `<ProposalBlocksEditor key={hasBlocks ? "filled" : "empty"} … />` НЕДОСТАТОЧНО (генерация при hasBlocks=true не сменит key). Правильнее: веди счётчик ревизий. Добавь `const [rev, setRev] = useState(0)`, вызывай `setRev((r) => r + 1)` в `generate()` после `setBlocks`, и поставь `key={rev}` на `<ProposalBlocksEditor>`. Это пере-монтирует редактор с новыми `defaultValue` после AI-генерации (правка по blur при этом работает без ремоунта).

- [ ] **Step 5: Run, confirm PASS** — `npm run test -- src/components/estimate/ProposalTab.test.tsx` (4 passed)

- [ ] **Step 6: Commit**
```bash
git add frontend/src/components/estimate/ProposalBlocksEditor.tsx frontend/src/components/estimate/ProposalTab.tsx frontend/src/components/estimate/ProposalTab.test.tsx
git commit -m "feat(4b1): proposal tab — AI generate + manual block editor"
```

---

## Task 6: Кнопки экспорта (Excel/PDF + уровень)

**Files:**
- Create: `frontend/src/components/estimate/ExportButtons.tsx`
- Test: `frontend/src/components/estimate/ExportButtons.test.tsx`

- [ ] **Step 1: Failing test** — `frontend/src/components/estimate/ExportButtons.test.tsx`:
```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ExportButtons from "./ExportButtons";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function stubFetch() {
  const f = vi.fn(async () => new Response(new Blob(["x"]), { status: 200 }));
  vi.stubGlobal("fetch", f);
  // jsdom: подменяем URL.createObjectURL/anchor click
  vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
  return f;
}

describe("ExportButtons", () => {
  it("downloads xlsx with selected level", async () => {
    const f = stubFetch();
    render(<ExportButtons estimateId={7} />);
    await userEvent.selectOptions(screen.getByLabelText("Уровень"), "cover");
    await userEvent.click(screen.getByText("Скачать Excel"));
    await vi.waitFor(() => {
      expect(f.mock.calls[0][0]).toBe("/api/estimates/7/export.xlsx?level=cover");
    });
  });

  it("downloads pdf (default level full)", async () => {
    const f = stubFetch();
    render(<ExportButtons estimateId={7} />);
    await userEvent.click(screen.getByText("Скачать PDF"));
    await vi.waitFor(() => {
      expect(f.mock.calls[0][0]).toBe("/api/estimates/7/export.pdf?level=full");
    });
  });
});
```

- [ ] **Step 2: Run, confirm FAIL** — `npm run test -- src/components/estimate/ExportButtons.test.tsx`

- [ ] **Step 3: Create `frontend/src/components/estimate/ExportButtons.tsx`:**
```tsx
import { useState } from "react";
import { downloadExport, type ExportLevel } from "../../api/export";

const LEVELS: { value: ExportLevel; label: string }[] = [
  { value: "full", label: "Полное КП" },
  { value: "cover", label: "Титул + смета" },
  { value: "estimate", label: "Только смета" },
];

export default function ExportButtons({ estimateId }: { estimateId: number }) {
  const [level, setLevel] = useState<ExportLevel>("full");
  const [error, setError] = useState("");

  async function dl(fmt: "xlsx" | "pdf") {
    setError("");
    try {
      await downloadExport(estimateId, fmt, level);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка скачивания");
    }
  }

  return (
    <div className="grid gap-2 text-sm">
      <label className="grid max-w-xs gap-1">
        <span className="text-stone-500">Уровень</span>
        <select aria-label="Уровень" value={level} onChange={(e) => setLevel(e.target.value as ExportLevel)}
          className="rounded border border-stone-300 px-2 py-1">
          {LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
        </select>
      </label>
      <div className="flex gap-2">
        <button onClick={() => dl("xlsx")} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Скачать Excel</button>
        <button onClick={() => dl("pdf")} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Скачать PDF</button>
      </div>
      {error && <p role="alert" className="text-red-600">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 4: Run, confirm PASS** — `npm run test -- src/components/estimate/ExportButtons.test.tsx` (2 passed)

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/estimate/ExportButtons.tsx frontend/src/components/estimate/ExportButtons.test.tsx
git commit -m "feat(4b1): export buttons (xlsx/pdf + level)"
```

---

## Task 7: Менеджер публичных ссылок

**Files:**
- Create: `frontend/src/components/estimate/PublicLinksManager.tsx`
- Test: `frontend/src/components/estimate/PublicLinksManager.test.tsx`

- [ ] **Step 1: Failing test** — `frontend/src/components/estimate/PublicLinksManager.test.tsx`:
```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PublicLinksManager from "./PublicLinksManager";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
const LINK = { id: 3, estimate_id: 7, token: "abc123", level: "full", expires_at: null,
  watermark_enabled: false, watermark_text: "", revoked: false, created_at: "2026-06-13T00:00:00Z" };
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("PublicLinksManager", () => {
  it("lists links and shows public url", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([LINK])));
    render(<PublicLinksManager estimateId={7} canEdit={true} />);
    expect(await screen.findByText(/\/p\/abc123/)).toBeInTheDocument();
  });

  it("creates a link (POST) and revokes it (DELETE)", async () => {
    const f = vi.fn(async (url: string, init?: RequestInit) => {
      const m = init?.method ?? "GET";
      if (m === "POST") return json(LINK, 201);
      if (m === "DELETE") return new Response(null, { status: 204 });
      return json([LINK]);
    });
    vi.stubGlobal("fetch", f);
    render(<PublicLinksManager estimateId={7} canEdit={true} />);
    await userEvent.click(screen.getByText("Создать ссылку"));
    await vi.waitFor(() => expect(f.mock.calls.some((c) => (c[1] as RequestInit | undefined)?.method === "POST")).toBe(true));
    await userEvent.click(await screen.findByText("Отозвать"));
    await vi.waitFor(() => expect(f.mock.calls.some((c) => (c[1] as RequestInit | undefined)?.method === "DELETE")).toBe(true));
  });

  it("hides create/revoke for viewer", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([LINK])));
    render(<PublicLinksManager estimateId={7} canEdit={false} />);
    await screen.findByText(/\/p\/abc123/);
    expect(screen.queryByText("Создать ссылку")).not.toBeInTheDocument();
    expect(screen.queryByText("Отозвать")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run, confirm FAIL** — `npm run test -- src/components/estimate/PublicLinksManager.test.tsx`

- [ ] **Step 3: Create `frontend/src/components/estimate/PublicLinksManager.tsx`:**
```tsx
import { useEffect, useState } from "react";
import { createLink, listLinks, revokeLink, type PublicLink } from "../../api/publicLinks";

const LEVELS = [
  { value: "full", label: "Полное КП" },
  { value: "cover", label: "Титул + смета" },
  { value: "estimate", label: "Только смета" },
];
const EXPIRY = [
  { value: "", label: "Без срока" },
  { value: "7", label: "7 дней" },
  { value: "30", label: "30 дней" },
];

function expiryToIso(days: string): string | null {
  if (!days) return null;
  const d = new Date();
  d.setDate(d.getDate() + Number(days));
  return d.toISOString();
}

export default function PublicLinksManager({ estimateId, canEdit }: { estimateId: number; canEdit: boolean }) {
  const [links, setLinks] = useState<PublicLink[]>([]);
  const [level, setLevel] = useState("full");
  const [expiry, setExpiry] = useState("");
  const [wm, setWm] = useState(false);
  const [wmText, setWmText] = useState("ОБРАЗЕЦ");
  const [error, setError] = useState("");

  useEffect(() => {
    listLinks(estimateId).then(setLinks).catch(() => setLinks([]));
  }, [estimateId]);

  async function create() {
    setError("");
    try {
      const link = await createLink(estimateId, {
        level, expires_at: expiryToIso(expiry),
        watermark_enabled: wm, watermark_text: wm ? wmText : "",
      });
      setLinks((ls) => [link, ...ls]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка создания");
    }
  }

  async function revoke(id: number) {
    setError("");
    try {
      await revokeLink(id);
      setLinks((ls) => ls.map((l) => (l.id === id ? { ...l, revoked: true } : l)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка отзыва");
    }
  }

  const publicUrl = (token: string) => `${window.location.origin}/p/${token}`;

  return (
    <div className="grid gap-3 text-sm">
      <h3 className="font-serif text-stone-800">Публичные ссылки</h3>
      {error && <p role="alert" className="text-red-600">{error}</p>}
      {canEdit && (
        <div className="flex flex-wrap items-center gap-2">
          <select aria-label="Уровень ссылки" value={level} onChange={(e) => setLevel(e.target.value)}
            className="rounded border border-stone-300 px-2 py-1">
            {LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
          <select aria-label="Срок" value={expiry} onChange={(e) => setExpiry(e.target.value)}
            className="rounded border border-stone-300 px-2 py-1">
            {EXPIRY.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
          </select>
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={wm} onChange={(e) => setWm(e.target.checked)} /> водяной знак
          </label>
          {wm && (
            <input aria-label="Текст водяного знака" value={wmText} onChange={(e) => setWmText(e.target.value)}
              className="rounded border border-stone-300 px-2 py-1" />
          )}
          <button onClick={create} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Создать ссылку</button>
        </div>
      )}
      <ul className="grid gap-1">
        {links.map((l) => (
          <li key={l.id} className="flex flex-wrap items-center gap-2">
            <span className={l.revoked ? "text-stone-400 line-through" : "text-stone-700"}>{publicUrl(l.token)}</span>
            <span className="text-stone-400">· {l.level}{l.expires_at ? ` · до ${new Date(l.expires_at).toLocaleDateString()}` : ""}</span>
            {!l.revoked && (
              <button onClick={() => navigator.clipboard?.writeText(publicUrl(l.token))} className="text-stone-600 underline">копировать</button>
            )}
            {canEdit && !l.revoked && (
              <button onClick={() => revoke(l.id)} className="text-red-700">Отозвать</button>
            )}
            {l.revoked && <span className="text-stone-400">отозвана</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Run, confirm PASS** — `npm run test -- src/components/estimate/PublicLinksManager.test.tsx` (3 passed)

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/estimate/PublicLinksManager.tsx frontend/src/components/estimate/PublicLinksManager.test.tsx
git commit -m "feat(4b1): public links manager (create/list/revoke)"
```

---

## Task 8: Вкладка «Поделиться» + интеграция вкладок + общий прогон

**Files:**
- Create: `frontend/src/components/estimate/ShareTab.tsx`
- Modify: `frontend/src/pages/EstimateEditorPage.tsx` (раскомментировать `kp`/`share`, если были заглушки)
- Test: `frontend/src/components/estimate/ShareTab.test.tsx`

- [ ] **Step 1: Failing test** — `frontend/src/components/estimate/ShareTab.test.tsx`:
```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import ShareTab from "./ShareTab";

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("ShareTab", () => {
  it("renders export buttons and public links section", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json([])));  // listLinks → []
    render(<ShareTab estimateId={7} canEdit={true} />);
    expect(screen.getByText("Скачать Excel")).toBeInTheDocument();
    expect(screen.getByText("Скачать PDF")).toBeInTheDocument();
    expect(await screen.findByText("Публичные ссылки")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run, confirm FAIL** — `npm run test -- src/components/estimate/ShareTab.test.tsx`

- [ ] **Step 3: Create `frontend/src/components/estimate/ShareTab.tsx`:**
```tsx
import ExportButtons from "./ExportButtons";
import PublicLinksManager from "./PublicLinksManager";

export default function ShareTab({ estimateId, canEdit }: { estimateId: number; canEdit: boolean }) {
  return (
    <div className="grid gap-6">
      <ExportButtons estimateId={estimateId} />
      <hr className="border-stone-200" />
      <PublicLinksManager estimateId={estimateId} canEdit={canEdit} />
    </div>
  );
}
```

- [ ] **Step 4: Finalize EstimateEditorPage integration** — убедиться, что в `EstimateEditorPage.tsx` вкладки подключены реально (из Task 4): `kp={<ProposalTab estimateId={est.id} initial={est.proposal} canEdit={e.canEdit} />}` и `share={<ShareTab estimateId={est.id} canEdit={e.canEdit} />}` (если в Task 4 стояли заглушки — заменить на реальные). Импорты `ProposalTab`/`ShareTab` присутствуют.

- [ ] **Step 5: Run, confirm PASS** — `npm run test -- src/components/estimate/ShareTab.test.tsx`

- [ ] **Step 6: Full frontend run** — `npm run test` (все фронт-тесты зелёные), `npm run build` (чисто), `npm run lint` (0 errors; warnings set-state-in-effect допустимы как в 3b).

- [ ] **Step 7: Commit**
```bash
git add frontend/src/components/estimate/ShareTab.tsx frontend/src/components/estimate/ShareTab.test.tsx frontend/src/pages/EstimateEditorPage.tsx
git commit -m "feat(4b1): share tab (export + public links) + wire estimate tabs"
```

---

## Финальная проверка

- [ ] `cd frontend && npm run test` — зелёно; `npm run build` чисто; `npm run lint` 0 errors.
- [ ] `cd backend && python -m pytest -q --ignore=tests/test_auth_yandex.py` — зелёно (правка EstimateDetail не ломает).
- [ ] Живой e2e (preview vite `smeta-frontend` + dockerized backend): открыть смету → вкладка КП (генерация даст 503, пока провайдер не настроен — плашка; ручной ввод сохраняется) → вкладка Поделиться (скачать Excel/PDF; создать публичную ссылку, открыть `/p/{token}`) → страница `/profile` (сохранить реквизиты). Скриншоты.
- [ ] Финальный холистический код-ревью.
- [ ] Merge в `main` + push (как 4a/AI); затем redeploy прода (`git pull && docker compose -p smetaapp up -d --build`).

## Self-Review (выполнено автором)

**Покрытие спека:** профиль `/profile` (Task 3) ✓; вкладки Смета/КП/Поделиться (Task 4) ✓; редактор блоков + AI-генерация + 503-плашка + advantages + canEdit (Task 5) ✓; экспорт Excel/PDF + уровень, fetch→Blob (Task 6, api/export Task 2) ✓; публичные ссылки create/list/revoke + копировать + публичный URL + viewer-гейт (Task 7) ✓; бэкенд отдаёт proposal (Task 1) ✓; типы proposal на EstimateDetail (Task 2) ✓; доступ canEdit для записи, экспорт для всех (Task 5/6/7) ✓; ссылка «Реквизиты» в шапке (Task 3) ✓.

**Согласованность типов:** `ProposalBlocks` (Task 2 `api/proposals.ts`) ↔ `EstimateDetail.proposal` (Task 2 estimates.ts) ↔ `ProposalTab`/`ProposalBlocksEditor` (Task 5). `downloadExport(id, fmt, level)` / `ExportLevel` (Task 2 export.ts) ↔ `ExportButtons` (Task 6). `PublicLink`/`createLink`/`revokeLink` (Task 2 publicLinks.ts) ↔ `PublicLinksManager` (Task 7). `EstimateTabs` props `{smeta,kp,share}` (Task 4) ↔ использование (Task 4/8). Тест-паттерн (json/stubUser/MemoryRouter+AuthProvider) единый.

**Плейсхолдеры:** код приведён полностью, без артефактов. Единственная важная деталь реализации (не плейсхолдер, а инструкция): `ProposalBlocksEditor` использует uncontrolled-инпуты (`defaultValue`), поэтому `ProposalTab` после AI-генерации пере-монтирует редактор через `key={rev}` (счётчик ревизий, инкремент в `generate()`), чтобы поля показали новые значения; правка по blur работает без ремоунта.
