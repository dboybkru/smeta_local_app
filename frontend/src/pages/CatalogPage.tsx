import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import {
  extractCharacteristics,
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
  const [extractMsg, setExtractMsg] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

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
  }, [q, supplierId, kind, offset, reloadKey]);

  function onFilterChange<T>(setter: (v: T) => void) {
    return (value: T) => {
      setOffset(0);
      setter(value);
    };
  }

  const supplierName = (id: number) => suppliers.find((s) => s.id === id)?.name ?? "—";

  async function runExtract() {
    setExtractMsg("✨ AI: извлекаю характеристики…");
    try {
      for (let i = 0; i < 200; i++) {
        const r = await extractCharacteristics(supplierId === "" ? undefined : supplierId);
        if (r.remaining <= 0) { setExtractMsg("✓ Готово."); break; }
        setExtractMsg(`✨ AI: извлекаю… осталось ${r.remaining}`);
      }
      setReloadKey((k) => k + 1);
    } catch (err) {
      setExtractMsg(err instanceof Error ? err.message : "Ошибка извлечения");
    }
  }

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
          <button
            onClick={() => void runExtract()}
            className="rounded border border-stone-700 px-3 py-1 text-stone-700"
          >
            ✨ AI: извлечь характеристики
          </button>
          {extractMsg && <span className="text-stone-500">{extractMsg}</span>}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-stone-300 text-left text-stone-500">
              <th className="py-2">Артикул</th>
              <th>Наименование</th>
              <th>Поставщик</th>
              <th>Ед.</th>
              <th>Характеристики</th>
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
                <td className="max-w-xs text-xs text-stone-500">
                  {it.characteristics
                    ? Object.entries(it.characteristics).slice(0, 4).map(([k, v]) => (
                        <span key={k} className="mr-1 inline-block rounded bg-stone-100 px-1">{k}: {v}</span>
                      ))
                    : ""}
                </td>
                {levels.map((l) => (
                  <td key={l.id} className="text-right tabular-nums">
                    {it.prices[String(l.id)] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          </table>
        </div>

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
