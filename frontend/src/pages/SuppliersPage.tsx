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
      const created = await createSupplier(name.trim());
      setName("");
      setSuppliers((prev) => [...prev, created]);
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
