import { useEffect, useState } from "react";
import { clearUsage, getUsage, type UsageSummary } from "../../api/ai";

type Props = { version: number; onChanged: () => void };

export default function UsageSection({ version, onChanged }: Props) {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      setUsage(await getUsage());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }
  useEffect(() => { void load(); }, [version]);

  async function reset() {
    if (!window.confirm("Очистить журнал расходов AI?")) return;
    setError("");
    try {
      await clearUsage();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка очистки");
    }
  }

  const fmtCost = (c: string | null) => (c == null ? "—" : `${c} ₽`);

  return (
    <section className="mt-10">
      <div className="mb-3 flex items-center gap-4">
        <h2 className="font-serif text-lg text-stone-900">Расходы</h2>
        {usage && usage.total_calls > 0 && (
          <button onClick={() => void reset()} className="rounded border border-red-700 px-2 py-1 text-sm text-red-700">
            Сбросить
          </button>
        )}
      </div>
      {error && <p role="alert" className="mb-2 text-red-600">{error}</p>}

      {!usage || usage.total_calls === 0 ? (
        <p className="text-stone-500">Расходов пока нет — счётчик появится после первого AI-вызова.</p>
      ) : (
        <>
          <p className="mb-3 text-sm text-stone-700">
            Всего вызовов: <b>{usage.total_calls}</b>; суммарно: <b>{fmtCost(usage.total_cost_rub)}</b>
            <span className="ml-2 text-xs text-stone-400">(стоимость — где провайдер её отдаёт, напр. AITunnel)</span>
          </p>
          <table className="w-full border-collapse text-sm">
            <thead><tr className="border-b border-stone-300 text-left text-stone-500">
              <th className="py-2">Провайдер</th><th>Модель</th><th>Вызовов</th><th>Токены (вход/выход)</th><th>Стоимость</th></tr></thead>
            <tbody>
              {usage.by_model.map((r) => (
                <tr key={`${r.provider_name}/${r.model_id}`} className="border-b border-stone-200">
                  <td className="py-2 text-stone-500">{r.provider_name}</td>
                  <td className="font-mono text-xs">{r.model_id}</td>
                  <td>{r.calls}</td>
                  <td>{r.prompt_tokens} / {r.completion_tokens}</td>
                  <td>{fmtCost(r.cost_rub)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
