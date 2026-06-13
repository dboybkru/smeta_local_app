import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import { useAuth } from "../auth/AuthContext";
import {
  createEstimate,
  deleteEstimate,
  listClients,
  listEstimates,
  type Client,
  type Estimate,
} from "../api/estimates";

export default function EstimatesListPage() {
  const { user } = useAuth();
  const canEdit = user == null || user?.role === "estimator" || user?.role === "admin";
  const navigate = useNavigate();
  const [items, setItems] = useState<Estimate[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [name, setName] = useState("");
  const [clientId, setClientId] = useState<number | "">("");
  const [vatEnabled, setVatEnabled] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [est, cl] = await Promise.all([listEstimates(), listClients()]);
      setItems(est);
      setClients(cl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }
  useEffect(() => {
    void load();
  }, []);

  async function create() {
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const est = await createEstimate({
        object_name: name.trim(),
        client_id: clientId === "" ? null : clientId,
        vat_enabled: vatEnabled,
      });
      navigate(`/estimates/${est.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setError("");
    try {
      await deleteEstimate(id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить");
    }
  }

  const clientName = (id: number | null) =>
    id == null ? "—" : (clients.find((c) => c.id === id)?.name ?? "—");

  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8">
        <h1 className="mb-4 font-serif text-xl text-stone-900">Сметы</h1>
        {error && <p role="alert" className="mb-3 text-red-600">{error}</p>}

        {canEdit && (
          <div className="mb-6 flex flex-wrap items-end gap-2 text-sm">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название объекта"
              className="min-w-64 rounded border border-stone-300 px-2 py-1"
            />
            <select
              value={clientId}
              onChange={(e) => setClientId(e.target.value === "" ? "" : Number(e.target.value))}
              className="rounded border border-stone-300 px-2 py-1"
            >
              <option value="">Без клиента</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={vatEnabled} onChange={(e) => setVatEnabled(e.target.checked)} />
              НДС
            </label>
            <button
              onClick={() => void create()}
              disabled={busy}
              className="rounded border border-stone-700 px-3 py-1 text-stone-700 disabled:opacity-50"
            >
              Создать смету
            </button>
          </div>
        )}

        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-stone-300 text-left text-stone-500">
              <th className="py-2">Объект</th>
              <th>Клиент</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((e) => (
              <tr key={e.id} className="border-b border-stone-200">
                <td className="py-2">
                  <Link to={`/estimates/${e.id}`} className="text-stone-900 hover:underline">
                    {e.object_name || "Без названия"}
                  </Link>
                </td>
                <td className="text-stone-500">{clientName(e.client_id)}</td>
                <td className="text-stone-500">{e.status}</td>
                <td className="text-right">
                  {canEdit && (
                    <button
                      onClick={() => void remove(e.id)}
                      className="rounded border border-red-700 px-2 py-1 text-red-700"
                    >
                      Удалить
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </main>
    </div>
  );
}
