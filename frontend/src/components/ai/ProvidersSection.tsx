import { Fragment, useEffect, useState } from "react";
import {
  createProvider, deleteProvider, listProviders, refreshModels, updateProvider,
  type AuthStyle, type Provider, type ProviderPatch,
} from "../../api/ai";

type Props = { version: number; onChanged: () => void };

export default function ProvidersSection({ version, onChanged }: Props) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [authStyle, setAuthStyle] = useState<AuthStyle>("bearer");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  // инлайн-редактирование провайдера
  const [editId, setEditId] = useState<number | null>(null);
  const [eBaseUrl, setEBaseUrl] = useState("");
  const [eAuth, setEAuth] = useState<AuthStyle>("bearer");
  const [eKey, setEKey] = useState("");

  async function load() {
    try {
      setProviders(await listProviders());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }
  useEffect(() => { void load(); }, [version]);

  async function add() {
    if (!name.trim() || !baseUrl.trim()) return;
    setError(""); setNotice("");
    try {
      await createProvider({
        name: name.trim(), base_url: baseUrl.trim(), auth_style: authStyle, api_key: apiKey, enabled: true,
      });
      setName(""); setBaseUrl(""); setApiKey(""); setAuthStyle("bearer");
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка создания");
    }
  }

  async function refresh(p: Provider) {
    setError(""); setNotice("");
    try {
      const r = await refreshModels(p.id);
      const extra = r.updated ? `, цены дозаполнены: ${r.updated}` : "";
      setNotice(`Импортировано моделей: ${r.imported}${extra}`);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка импорта");
    }
  }

  async function toggleEnabled(p: Provider) {
    setError("");
    try {
      await updateProvider(p.id, { enabled: !p.enabled });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка обновления");
    }
  }

  function startEdit(p: Provider) {
    setEditId(p.id);
    setEBaseUrl(p.base_url);
    setEAuth(p.auth_style as AuthStyle);
    setEKey("");
    setError(""); setNotice("");
  }

  function cancelEdit() {
    setEditId(null);
    setEKey("");
  }

  async function saveEdit(p: Provider) {
    if (!eBaseUrl.trim()) return;
    setError(""); setNotice("");
    const patch: ProviderPatch = { base_url: eBaseUrl.trim(), auth_style: eAuth };
    if (eKey.trim()) patch.api_key = eKey.trim();
    try {
      await updateProvider(p.id, patch);
      setNotice(`Провайдер «${p.name}» обновлён`);
      cancelEdit();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка обновления провайдера");
    }
  }

  async function remove(p: Provider) {
    if (!window.confirm(`Удалить провайдера «${p.name}»? Его модели тоже удалятся.`)) return;
    setError("");
    try {
      await deleteProvider(p.id);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    }
  }

  return (
    <section className="mb-10">
      <h2 className="mb-3 font-serif text-lg text-stone-900">Провайдеры</h2>
      {error && <p role="alert" className="mb-2 text-red-600">{error}</p>}
      {notice && <p className="mb-2 text-green-700">{notice}</p>}

      <div className="mb-2 flex flex-wrap items-end gap-2">
        <label className="text-sm text-stone-600"><span className="mb-1 block">Название</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Название"
            className="rounded border border-stone-300 px-2 py-1" />
        </label>
        <label className="text-sm text-stone-600"><span className="mb-1 block">Base URL</span>
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.vsegpt.ru/v1"
            className="w-64 rounded border border-stone-300 px-2 py-1" />
        </label>
        <label className="text-sm text-stone-600"><span className="mb-1 block">Авторизация</span>
          <select aria-label="Авторизация" value={authStyle} onChange={(e) => setAuthStyle(e.target.value as AuthStyle)}
            className="rounded border border-stone-300 px-2 py-1">
            <option value="bearer">Bearer</option>
            <option value="x_api_key">X-Api-Key</option>
          </select>
        </label>
        <label className="text-sm text-stone-600"><span className="mb-1 block">Ключ</span>
          <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="API-ключ"
            className="rounded border border-stone-300 px-2 py-1" />
        </label>
        <button onClick={() => void add()} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Добавить</button>
      </div>
      <p className="mb-4 text-xs text-stone-500">
        Примеры: AITunnel — https://api.aitunnel.ru/v1/ ; VseGPT — https://api.vsegpt.ru/v1 .
        Оба OpenAI-совместимы — для /v1/chat обычно нужен <b>Bearer</b>. Если получаете 403 — переключите авторизацию на Bearer.
      </p>

      {providers.length === 0 ? (
        <p className="text-stone-500">Провайдеров пока нет — добавьте первого.</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead><tr className="border-b border-stone-300 text-left text-stone-500">
            <th className="py-2">Название</th><th>Base URL</th><th>Авторизация</th><th>Ключ</th><th>Вкл.</th><th /></tr></thead>
          <tbody>
            {providers.map((p) => (
              <Fragment key={p.id}>
                <tr className="border-b border-stone-200">
                  <td className="py-2">{p.name}</td>
                  <td className="text-stone-500">{p.base_url}</td>
                  <td>{p.auth_style}</td>
                  <td>{p.has_key ? "ключ задан" : "нет ключа"}</td>
                  <td><input type="checkbox" aria-label={`Включён ${p.name}`} checked={p.enabled} onChange={() => void toggleEnabled(p)} /></td>
                  <td className="space-x-2 text-right">
                    <button onClick={() => void refresh(p)} className="rounded border border-stone-500 px-2 py-1 text-stone-600">Импорт моделей</button>
                    <button onClick={() => startEdit(p)} className="rounded border border-stone-500 px-2 py-1 text-stone-600">Изменить</button>
                    <button onClick={() => void remove(p)} className="rounded border border-red-700 px-2 py-1 text-red-700">Удалить</button>
                  </td>
                </tr>
                {editId === p.id && (
                  <tr className="border-b border-stone-200 bg-stone-50">
                    <td colSpan={6} className="p-3">
                      <div className="flex flex-wrap items-end gap-2">
                        <label className="text-sm text-stone-600"><span className="mb-1 block">Base URL</span>
                          <input aria-label={`Base URL ${p.name}`} value={eBaseUrl}
                            onChange={(e) => setEBaseUrl(e.target.value)}
                            className="w-64 rounded border border-stone-300 px-2 py-1" />
                        </label>
                        <label className="text-sm text-stone-600"><span className="mb-1 block">Авторизация</span>
                          <select aria-label={`Авторизация ${p.name}`} value={eAuth}
                            onChange={(e) => setEAuth(e.target.value as AuthStyle)}
                            className="rounded border border-stone-300 px-2 py-1">
                            <option value="bearer">Bearer</option>
                            <option value="x_api_key">X-Api-Key</option>
                          </select>
                        </label>
                        <label className="text-sm text-stone-600"><span className="mb-1 block">Новый ключ (пусто — не менять)</span>
                          <input type="password" aria-label={`Новый ключ ${p.name}`} value={eKey}
                            onChange={(e) => setEKey(e.target.value)} placeholder="оставьте пустым"
                            className="rounded border border-stone-300 px-2 py-1" />
                        </label>
                        <button onClick={() => void saveEdit(p)} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Сохранить</button>
                        <button onClick={cancelEdit} className="text-stone-500">Отмена</button>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
