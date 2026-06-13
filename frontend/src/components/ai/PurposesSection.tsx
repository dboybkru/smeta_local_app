import { useEffect, useState } from "react";
import {
  listModels, listProviders, listPurposes, recommend, testPurpose, updatePurpose,
  type AiModel, type Provider, type Purpose, type Recommendation,
} from "../../api/ai";
import { ApiError } from "../../api/client";

type Props = { version: number; onChanged: () => void };

export default function PurposesSection({ version, onChanged }: Props) {
  const [purposes, setPurposes] = useState<Purpose[]>([]);
  const [models, setModels] = useState<AiModel[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [recs, setRecs] = useState<Record<string, Recommendation>>({});
  const [tests, setTests] = useState<Record<string, { ok: boolean; detail: string }>>({});
  const [error, setError] = useState("");

  async function load() {
    try {
      const [pp, ms, ps] = await Promise.all([listPurposes(), listModels(), listProviders()]);
      setPurposes(pp); setModels(ms); setProviders(ps);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }
  useEffect(() => { void load(); }, [version]);

  const enabledModels = models.filter((m) => m.enabled);
  function modelLabel(m: AiModel) {
    const prov = providers.find((p) => p.id === m.provider_id)?.name ?? `#${m.provider_id}`;
    return `${prov} / ${m.label}`;
  }

  async function setModel(p: Purpose, field: "primary_model_id" | "fallback_model_id", value: string) {
    const id = value === "" ? null : Number(value);
    setError("");
    try {
      await updatePurpose(p.key, { [field]: id });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function toggleEnabled(p: Purpose) {
    setError("");
    try {
      await updatePurpose(p.key, { enabled: !p.enabled });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка сохранения");
    }
  }

  async function loadRecs() {
    setError("");
    try {
      const list = await recommend();
      const map: Record<string, Recommendation> = {};
      for (const r of list) map[r.purpose_key] = r;
      setRecs(map);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503)
        setError("Советник недоступен: цель «router» не настроена");
      else setError(err instanceof Error ? err.message : "Ошибка советника");
    }
  }

  async function applyRec(p: Purpose, rec: Recommendation) {
    const provId = providers.find((pr) => pr.name === rec.provider)?.id;
    const model = models.find((m) => m.model_id === rec.model_id && (provId == null || m.provider_id === provId));
    if (!model) { setError("Сначала импортируйте модели этого провайдера"); return; }
    await setModel(p, "primary_model_id", String(model.id));
  }

  async function runTest(p: Purpose) {
    setError("");
    try {
      const result = await testPurpose(p.key);
      setTests((cur) => ({ ...cur, [p.key]: result }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка теста");
    }
  }

  return (
    <section>
      <h2 className="mb-3 font-serif text-lg text-stone-900">Цели</h2>
      {error && <p role="alert" className="mb-2 text-red-600">{error}</p>}

      <table className="w-full border-collapse text-sm">
        <thead><tr className="border-b border-stone-300 text-left text-stone-500">
          <th className="py-2">Цель</th><th>Основная модель</th><th>Резервная</th><th>Вкл.</th><th>Советник</th><th>Тест</th></tr></thead>
        <tbody>
          {purposes.map((p) => {
            const rec = recs[p.key];
            const t = tests[p.key];
            return (
              <tr key={p.key} className="border-b border-stone-200 align-top">
                <td className="py-2"><span className="block">{p.title}</span><span className="text-xs text-stone-400">{p.key}</span></td>
                <td>
                  <select aria-label={`Основная модель ${p.key}`} value={p.primary_model_id ?? ""}
                    onChange={(e) => void setModel(p, "primary_model_id", e.target.value)}
                    className="rounded border border-stone-300 px-1 py-0.5">
                    <option value="">— нет —</option>
                    {enabledModels.map((m) => <option key={m.id} value={m.id}>{modelLabel(m)}</option>)}
                  </select>
                </td>
                <td>
                  <select aria-label={`Резервная модель ${p.key}`} value={p.fallback_model_id ?? ""}
                    onChange={(e) => void setModel(p, "fallback_model_id", e.target.value)}
                    className="rounded border border-stone-300 px-1 py-0.5">
                    <option value="">— нет —</option>
                    {enabledModels.map((m) => <option key={m.id} value={m.id}>{modelLabel(m)}</option>)}
                  </select>
                </td>
                <td><input type="checkbox" aria-label={`Включена ${p.key}`} checked={p.enabled} onChange={() => void toggleEnabled(p)} /></td>
                <td>
                  <button onClick={() => void loadRecs()} className="rounded border border-stone-500 px-2 py-1 text-stone-600">Подобрать</button>
                  {rec && (
                    <div className="mt-1 text-xs text-stone-600">
                      <div>{rec.provider} / {rec.model_id}</div>
                      <div className="text-stone-400">{rec.rationale}</div>
                      <button onClick={() => void applyRec(p, rec)} className="mt-1 rounded border border-stone-700 px-2 py-0.5 text-stone-700">Применить</button>
                    </div>
                  )}
                </td>
                <td>
                  <button onClick={() => void runTest(p)} className="rounded border border-stone-500 px-2 py-1 text-stone-600">Тест</button>
                  {t && <span className={`ml-1 ${t.ok ? "text-green-700" : "text-red-600"}`}>{t.ok ? "✓" : `✗ ${t.detail}`}</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
