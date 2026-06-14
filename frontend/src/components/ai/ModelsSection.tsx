import { useEffect, useState } from "react";
import {
  deleteAllModels, deleteModel, listModels, listProviders, manufacturer, testModel, updateModel,
  type AiModel, type ModelPatch, type Provider,
} from "../../api/ai";

type Props = { version: number; onChanged: () => void };

export default function ModelsSection({ version, onChanged }: Props) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [models, setModels] = useState<AiModel[]>([]);
  const [filter, setFilter] = useState<number | "">("");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [tests, setTests] = useState<Record<number, { ok: boolean; detail: string } | "...">>({});

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

  async function toggleFromSearch(m: AiModel) {
    await save(m, { enabled: !m.enabled });
    setQuery("");
  }

  async function removeAll() {
    const scope = filter === "" ? "ВСЕ модели" : "все модели этого провайдера";
    if (!window.confirm(`Удалить ${scope}? Они снимутся со всех целей.`)) return;
    setError("");
    try {
      await deleteAllModels(filter === "" ? undefined : filter);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    }
  }

  async function runTest(m: AiModel) {
    setTests((cur) => ({ ...cur, [m.id]: "..." }));
    try {
      const res = await testModel(m.id);
      setTests((cur) => ({ ...cur, [m.id]: res }));
    } catch (err) {
      setTests((cur) => ({ ...cur, [m.id]: { ok: false, detail: err instanceof Error ? err.message : "Ошибка" } }));
    }
  }

  const q = query.trim().toLowerCase();
  const matches = q
    ? models.filter((m) => `${m.model_id} ${m.label}`.toLowerCase().includes(q)).slice(0, 12)
    : [];
  const enabledModels = models.filter((m) => m.enabled);

  // группировка включённых: провайдер → производитель → модели (отсортировано)
  function groupedEnabled(): [string, [string, AiModel[]][]][] {
    const byProv: Record<string, Record<string, AiModel[]>> = {};
    for (const m of enabledModels) {
      const prov = providerName(m.provider_id);
      const man = manufacturer(m.model_id);
      ((byProv[prov] ??= {})[man] ??= []).push(m);
    }
    return Object.keys(byProv).sort().map((prov) => [
      prov,
      Object.keys(byProv[prov]).sort().map((man) => [man, byProv[prov][man]] as [string, AiModel[]]),
    ]);
  }

  function renderRow(m: AiModel) {
    return (
      <tr key={m.id} className="border-b border-stone-100 align-top">
        <td className="py-1 font-mono text-xs">{m.model_id}</td>
        <td>
          <input defaultValue={m.label} aria-label={`Название ${m.model_id}`}
            onBlur={(e) => { if (e.target.value !== m.label) void save(m, { label: e.target.value }); }}
            className="w-32 rounded border border-stone-300 px-1 py-0.5" />
        </td>
        <td>
          <input defaultValue={m.input_price ?? ""} aria-label={`Вход ${m.model_id}`}
            onBlur={(e) => { const v = e.target.value.trim() === "" ? null : e.target.value.trim(); if (v !== (m.input_price ?? null)) void save(m, { input_price: v }); }}
            className="w-16 rounded border border-stone-300 px-1 py-0.5" />
        </td>
        <td>
          <input defaultValue={m.output_price ?? ""} aria-label={`Выход ${m.model_id}`}
            onBlur={(e) => { const v = e.target.value.trim() === "" ? null : e.target.value.trim(); if (v !== (m.output_price ?? null)) void save(m, { output_price: v }); }}
            className="w-16 rounded border border-stone-300 px-1 py-0.5" />
        </td>
        <td>
          <input defaultValue={m.strengths} aria-label={`Сильные стороны ${m.model_id}`}
            onBlur={(e) => { if (e.target.value !== m.strengths) void save(m, { strengths: e.target.value }); }}
            className="w-40 rounded border border-stone-300 px-1 py-0.5" />
        </td>
        <td><input type="checkbox" aria-label={`Включена ${m.model_id}`} checked={m.enabled} onChange={() => void save(m, { enabled: !m.enabled })} /></td>
        <td className="space-x-2 whitespace-nowrap text-right">
          <button onClick={() => void runTest(m)} className="rounded border border-stone-500 px-2 py-1 text-stone-600">Тест</button>
          {tests[m.id] === "..." && <span className="text-stone-400">…</span>}
          {tests[m.id] && tests[m.id] !== "..." && (
            <span className={(tests[m.id] as { ok: boolean }).ok ? "text-green-700" : "text-red-600"}>
              {(tests[m.id] as { ok: boolean; detail: string }).ok ? "✓" : `✗ ${(tests[m.id] as { ok: boolean; detail: string }).detail}`}
            </span>
          )}
          <button onClick={() => void remove(m)} className="rounded border border-red-700 px-2 py-1 text-red-700">Удалить</button>
        </td>
      </tr>
    );
  }

  return (
    <section className="mb-10">
      <h2 className="mb-3 font-serif text-lg text-stone-900">Модели</h2>
      {error && <p role="alert" className="mb-2 text-red-600">{error}</p>}

      <div className="mb-1 flex flex-wrap items-end gap-3">
        <label className="text-sm text-stone-600">
          <span className="mb-1 block">Провайдер</span>
          <select aria-label="Фильтр по провайдеру" value={filter}
            onChange={(e) => setFilter(e.target.value === "" ? "" : Number(e.target.value))}
            className="rounded border border-stone-300 px-2 py-1">
            <option value="">Все</option>
            {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <div className="relative text-sm text-stone-600">
          <span className="mb-1 block">Поиск модели</span>
          <input aria-label="Поиск модели" value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="напр. gpt-4o, claude, gemini"
            className="w-72 rounded border border-stone-300 px-2 py-1" />
          {q && (
            <ul className="absolute z-10 mt-1 max-h-72 w-72 overflow-auto rounded border border-stone-300 bg-white shadow">
              {matches.length === 0 ? (
                <li className="px-2 py-1 text-stone-400">Ничего не найдено</li>
              ) : matches.map((m) => (
                <li key={m.id}>
                  <button type="button" onClick={() => void toggleFromSearch(m)}
                    className="flex w-full items-center justify-between gap-2 px-2 py-1 text-left hover:bg-stone-100">
                    <span><span className="text-stone-400">{providerName(m.provider_id)} / </span>{m.label}</span>
                    <span className={m.enabled ? "text-green-700" : "text-stone-400"}>{m.enabled ? "вкл ✓" : "включить"}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="mb-4 flex items-center gap-3">
        <p className="text-xs text-stone-500">
          Всего моделей: {models.length}. Найдите модель в поиске и нажмите, чтобы включить.
          Цены и «сильные стороны» необязательны — советник узнаёт модель по названию.
        </p>
        {models.length > 0 && (
          <button onClick={() => void removeAll()} className="shrink-0 rounded border border-red-700 px-2 py-1 text-xs text-red-700">
            {filter === "" ? "Удалить все" : "Удалить все у провайдера"}
          </button>
        )}
      </div>

      <h3 className="mb-2 text-sm font-medium text-stone-700">Включённые модели ({enabledModels.length})</h3>
      {enabledModels.length === 0 ? (
        <p className="text-stone-500">Нет включённых моделей — найдите нужную через поиск выше и нажмите, чтобы включить.</p>
      ) : (
        groupedEnabled().map(([prov, mans]) => (
          <details key={prov} className="mb-2 rounded border border-stone-200">
            <summary className="cursor-pointer bg-stone-50 px-3 py-1.5 text-sm font-medium text-stone-700">
              {prov} ({mans.reduce((n, [, ms]) => n + ms.length, 0)})
            </summary>
            <div className="px-3 py-2">
              {mans.map(([man, ms]) => (
                <details key={man} className="mb-1">
                  <summary className="cursor-pointer py-1 text-sm text-stone-600">{man} ({ms.length})</summary>
                  <table className="w-full border-collapse text-sm">
                    <thead><tr className="border-b border-stone-200 text-left text-xs text-stone-400">
                      <th className="py-1">ID модели</th><th>Название</th><th>Вход</th><th>Выход</th><th>Сильные стороны</th><th>Вкл.</th><th /></tr></thead>
                    <tbody>{ms.map(renderRow)}</tbody>
                  </table>
                </details>
              ))}
            </div>
          </details>
        ))
      )}
    </section>
  );
}
