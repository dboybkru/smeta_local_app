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
