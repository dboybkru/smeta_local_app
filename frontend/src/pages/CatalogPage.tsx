import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import {
  clearCatalog,
  getFacets,
  listItems,
  listPriceLevels,
  listSuppliers,
  type CatalogItem,
  type PriceLevel,
  type Supplier,
} from "../api/catalog";
import { getJob, startCatalogExtract } from "../api/jobs";

const PAGE_SIZE = 50;

export function priceCellText(value: string | undefined, onRequest: boolean): string {
  if (onRequest) return "уточнить";
  return value ?? "—";
}

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
  const [facets, setFacets] = useState<Record<string, string[]>>({});
  const [selected, setSelected] = useState<Record<string, string>>({});

  useEffect(() => {
    Promise.all([listPriceLevels(), listSuppliers()])
      .then(([lv, sp]) => {
        setLevels(lv);
        setSuppliers(sp);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Ошибка загрузки"));
  }, []);

  useEffect(() => {
    setSelected({});
    void getFacets(supplierId === "" ? undefined : supplierId, kind || undefined)
      .then(setFacets).catch(() => setFacets({}));
  }, [supplierId, kind]);

  // Debounced search whenever filters change. Reset offset to 0 on filter change.
  useEffect(() => {
    const handle = setTimeout(() => {
      listItems({
        q: q || undefined,
        supplier_id: supplierId === "" ? undefined : supplierId,
        kind: kind || undefined,
        limit: PAGE_SIZE,
        offset,
        facets: Object.keys(selected).length ? selected : undefined,
      })
        .then((page) => {
          setItems(page.items);
          setTotal(page.total);
        })
        .catch((err) => setError(err instanceof Error ? err.message : "Ошибка поиска"));
    }, 250);
    return () => clearTimeout(handle);
  }, [q, supplierId, kind, offset, reloadKey, selected]);

  function onFilterChange<T>(setter: (v: T) => void) {
    return (value: T) => {
      setOffset(0);
      setter(value);
    };
  }

  const supplierName = (id: number) => suppliers.find((s) => s.id === id)?.name ?? "—";

  async function runExtract(force = false) {
    if (force && !window.confirm("Переизвлечь характеристики ЗАНОВО для всех позиций (сбросит текущие)? Это потратит токены AI.")) return;
    setExtractMsg("✨ AI: запускаю извлечение…");
    try {
      const job = await startCatalogExtract(supplierId === "" ? undefined : supplierId, force);
      for (let i = 0; i < 2000; i++) {
        const j = await getJob(job.id);
        if (j.status === "done") { setExtractMsg(j.total ? `✓ Готово (${j.processed}/${j.total}).` : "✓ Готово."); break; }
        if (j.status === "error") { setExtractMsg(`Ошибка: ${j.error || "проверьте цель «catalog_extract»"}`); break; }
        setExtractMsg(`✨ AI: ${j.message || "обработка…"}`);
        await new Promise((r) => setTimeout(r, 1500));
      }
      setReloadKey((k) => k + 1);
    } catch (err) {
      setExtractMsg(err instanceof Error ? err.message : "Ошибка извлечения");
    }
  }

  async function clearAll() {
    const scope = supplierId === "" ? "ВЕСЬ каталог" : "каталог этого поставщика";
    if (!window.confirm(`Очистить ${scope}? Позиции и их цены будут удалены (строки смет сохранятся, но отвяжутся от каталога).`)) return;
    setExtractMsg("");
    try {
      const r = await clearCatalog(supplierId === "" ? undefined : supplierId);
      setError("");
      setExtractMsg(`Удалено позиций: ${r.deleted}`);
      setOffset(0);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка очистки");
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
          <button
            onClick={() => void runExtract(true)}
            className="rounded border border-stone-500 px-3 py-1 text-stone-600"
          >
            Переизвлечь все
          </button>
          <button
            onClick={() => void clearAll()}
            className="rounded border border-red-700 px-3 py-1 text-red-700"
          >
            Очистить каталог
          </button>
          {extractMsg && <span className="text-stone-500">{extractMsg}</span>}
        </div>

        {Object.keys(facets).length > 0 && (
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
            {Object.entries(facets).map(([key, values]) => (
              <select key={key} aria-label={`Фильтр: ${key}`} value={selected[key] ?? ""}
                onChange={(e) => {
                  setOffset(0);
                  setSelected((s) => {
                    const next = { ...s };
                    if (e.target.value === "") delete next[key]; else next[key] = e.target.value;
                    return next;
                  });
                }}
                className="rounded border border-stone-300 px-2 py-1">
                <option value="">{key}: любое</option>
                {values.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            ))}
            {Object.keys(selected).length > 0 && (
              <button onClick={() => { setOffset(0); setSelected({}); }} className="text-stone-500">Сбросить фильтры</button>
            )}
          </div>
        )}

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
                <td className="text-stone-900">
                  {it.name}
                  {it.manufacturer && <span className="text-stone-400"> · {it.manufacturer}</span>}
                </td>
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
                    {priceCellText(it.prices[String(l.id)], it.price_on_request)}
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
