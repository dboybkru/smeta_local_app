import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import {
  createClient, listClients, suggestParties, updateClient,
  type Client, type ClientInput, type Suggestion,
} from "../api/clients";

const FIELDS: { key: keyof ClientInput; label: string }[] = [
  { key: "inn", label: "ИНН" }, { key: "kpp", label: "КПП" }, { key: "ogrn", label: "ОГРН" },
  { key: "address", label: "Юр. адрес" }, { key: "actual_address", label: "Факт. адрес" },
  { key: "contact_person", label: "Контактное лицо" }, { key: "phone", label: "Телефон" },
  { key: "email", label: "Email" }, { key: "bank_name", label: "Банк" },
  { key: "bank_account", label: "Расчётный счёт" }, { key: "bik", label: "БИК" },
];

const EMPTY: ClientInput = { name: "" };

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [editing, setEditing] = useState<ClientInput & { id?: number } | null>(null);
  const [query, setQuery] = useState("");
  const [sugg, setSugg] = useState<Suggestion[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try { setClients(await listClients()); }
    catch (e) { setError(e instanceof Error ? e.message : "Ошибка"); }
  }
  useEffect(() => { void load(); }, []);

  useEffect(() => {
    if (!query.trim()) { setSugg([]); return; }
    const h = setTimeout(() => { void suggestParties(query).then(setSugg).catch(() => setSugg([])); }, 300);
    return () => clearTimeout(h);
  }, [query]);

  function applySuggestion(s: Suggestion) {
    setEditing((c) => ({
      ...(c ?? EMPTY),
      name: s.name_short || s.value, inn: s.inn, kpp: s.kpp, ogrn: s.ogrn,
      address: s.address, contact_person: s.management, type: s.type,
    }));
    setQuery(""); setSugg([]);
  }

  function setField(key: keyof ClientInput, value: string) {
    setEditing((c) => ({ ...(c ?? EMPTY), [key]: value }));
  }

  async function save() {
    if (!editing || !editing.name.trim()) { setError("Укажите название"); return; }
    setError("");
    try {
      const { id, ...body } = editing;
      if (id) await updateClient(id, body);
      else await createClient(body);
      setEditing(null); setQuery(""); setSugg([]);
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : "Ошибка сохранения"); }
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8">
        <div className="mb-4 flex items-center gap-4">
          <h1 className="font-serif text-xl text-stone-900">Клиенты</h1>
          <button onClick={() => setEditing({ ...EMPTY })}
            className="rounded border border-stone-700 px-3 py-1 text-sm text-stone-700">Добавить клиента</button>
        </div>
        {error && <p role="alert" className="mb-3 text-red-600">{error}</p>}

        {editing && (
          <div className="mb-6 rounded border border-stone-300 bg-white p-4 text-sm">
            <div className="relative mb-3 max-w-md">
              <span className="mb-1 block text-stone-600">Найти по названию или ИНН (DaData)</span>
              <input aria-label="Поиск в DaData" value={query} onChange={(e) => setQuery(e.target.value)}
                placeholder="напр. Сбербанк или 7707083893"
                className="w-full rounded border border-stone-300 px-2 py-1" />
              {sugg.length > 0 && (
                <ul className="absolute z-10 mt-1 max-h-72 w-full overflow-auto rounded border border-stone-300 bg-white shadow">
                  {sugg.map((s, i) => (
                    <li key={i}>
                      <button type="button" onClick={() => applySuggestion(s)}
                        className="block w-full px-2 py-1 text-left hover:bg-stone-100">
                        {s.value} <span className="text-stone-400">ИНН {s.inn}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <label className="mb-2 block">
              <span className="mb-1 block text-stone-600">Название</span>
              <input aria-label="Название" value={editing.name}
                onChange={(e) => setField("name", e.target.value)}
                className="w-full max-w-md rounded border border-stone-300 px-2 py-1" />
            </label>
            <div className="grid max-w-2xl grid-cols-2 gap-2">
              {FIELDS.map(({ key, label }) => (
                <label key={key} className="block">
                  <span className="mb-1 block text-stone-600">{label}</span>
                  <input aria-label={label} value={(editing[key] as string) ?? ""}
                    onChange={(e) => setField(key, e.target.value)}
                    className="w-full rounded border border-stone-300 px-2 py-1" />
                </label>
              ))}
            </div>
            <div className="mt-3 space-x-2">
              <button onClick={() => void save()}
                className="rounded border border-stone-700 px-3 py-1 text-stone-700">Сохранить</button>
              <button onClick={() => { setEditing(null); setQuery(""); setSugg([]); }}
                className="text-stone-500">Отмена</button>
            </div>
          </div>
        )}

        <table className="w-full border-collapse text-sm">
          <thead><tr className="border-b border-stone-300 text-left text-stone-500">
            <th className="py-2">Название</th><th>ИНН</th><th>Телефон</th><th>Email</th><th /></tr></thead>
          <tbody>
            {clients.map((c) => (
              <tr key={c.id} className="border-b border-stone-200">
                <td className="py-2 text-stone-900">{c.name}</td>
                <td className="text-stone-500">{c.inn || "—"}</td>
                <td className="text-stone-500">{c.phone || "—"}</td>
                <td className="text-stone-500">{c.email || "—"}</td>
                <td className="text-right">
                  <button onClick={() => setEditing({ ...c })}
                    className="rounded border border-stone-500 px-2 py-1 text-stone-600">Изменить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {clients.length === 0 && <p className="mt-3 text-stone-500">Клиентов пока нет.</p>}
      </main>
    </div>
  );
}
