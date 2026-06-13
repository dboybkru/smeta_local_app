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
