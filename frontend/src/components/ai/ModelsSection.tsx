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
  const [query, setQuery] = useState("");
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

  const LIMIT = 50;
  const q = query.trim().toLowerCase();
  const matched = q
    ? models.filter((m) => `${m.model_id} ${m.label}`.toLowerCase().includes(q))
    : models;
  const visible = matched.slice(0, LIMIT);

  return (
    <section className="mb-10">
      <h2 className="mb-3 font-serif text-lg text-stone-900">Модели</h2>
      {error && <p role="alert" className="mb-2 text-red-600">{error}</p>}

      <div className="mb-2 flex flex-wrap items-end gap-3">
        <label className="text-sm text-stone-600">
          <span className="mb-1 block">Провайдер</span>
          <select aria-label="Фильтр по провайдеру" value={filter}
            onChange={(e) => setFilter(e.target.value === "" ? "" : Number(e.target.value))}
            className="rounded border border-stone-300 px-2 py-1">
            <option value="">Все</option>
            {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label className="text-sm text-stone-600">
          <span className="mb-1 block">Поиск модели</span>
          <input aria-label="Поиск модели" value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="напр. gpt-4o, claude, gemini"
            className="w-72 rounded border border-stone-300 px-2 py-1" />
        </label>
      </div>
      <p className="mb-4 text-xs text-stone-500">
        Всего моделей: {models.length}. Цены и «сильные стороны» необязательны — советник узнаёт модель по названию.
      </p>

      {models.length === 0 ? (
        <p className="text-stone-500">Моделей нет — добавьте провайдера и нажмите «Импорт моделей».</p>
      ) : matched.length === 0 ? (
        <p className="text-stone-500">Ничего не найдено по запросу «{query}».</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead><tr className="border-b border-stone-300 text-left text-stone-500">
            <th className="py-2">Провайдер</th><th>ID модели</th><th>Название</th><th>Вход (пров.)</th><th>Выход (пров.)</th><th>Сильные стороны</th><th>Вкл.</th><th /></tr></thead>
          <tbody>
            {visible.map((m) => (
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
      {matched.length > LIMIT && (
        <p className="mt-2 text-xs text-stone-500">
          Показаны первые {LIMIT} из {matched.length}. Уточните поиск, чтобы найти нужную модель.
        </p>
      )}
    </section>
  );
}
