import { useEffect, useMemo, useState } from "react";
import AppHeader from "../components/AppHeader";
import ColumnMapper from "../components/ColumnMapper";
import {
  createSupplier,
  extractCharacteristics,
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
import { ApiError } from "../api/client";

type Step = "upload" | "map" | "result";

const EMPTY_MAPPING: ColumnMapping = {
  name_col: 0, article_col: null, unit_col: null, category_col: null, price_cols: {},
};

export default function ImportPage() {
  const [step, setStep] = useState<Step>("upload");
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [levels, setLevels] = useState<PriceLevel[]>([]);
  const [supplierId, setSupplierId] = useState<number | "">("");
  const [creatingSupplier, setCreatingSupplier] = useState(false);
  const [newSupplierName, setNewSupplierName] = useState("");
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
  const [extractMsg, setExtractMsg] = useState("");

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
      void runExtract();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Импорт не удался");
    } finally {
      setBusy(false);
    }
  }

  async function runExtract() {
    if (supplierId === "") return;
    setExtractMsg("✨ AI: извлекаю характеристики…");
    try {
      for (let i = 0; i < 200; i++) {
        const r = await extractCharacteristics(supplierId);
        if (r.remaining <= 0) {
          setExtractMsg(r.processed > 0 || i > 0 ? "✓ Характеристики извлечены." : "");
          return;
        }
        setExtractMsg(`✨ AI: извлекаю характеристики… осталось ${r.remaining}`);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 503)
        setExtractMsg("AI не настроен — характеристики пропущены (настройте цель «catalog_extract»).");
      else setExtractMsg(err instanceof Error ? `Характеристики: ${err.message}` : "");
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
    setExtractMsg("");
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
            {extractMsg && <p className="text-stone-600">{extractMsg}</p>}
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
