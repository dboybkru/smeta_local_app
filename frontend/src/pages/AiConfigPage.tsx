import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import ProvidersSection from "../components/ai/ProvidersSection";
import ModelsSection from "../components/ai/ModelsSection";
import PurposesSection from "../components/ai/PurposesSection";
import UsageSection from "../components/ai/UsageSection";
import { getDadataSettings, saveDadata, getYandex, setYandex } from "../api/settings";

export default function AiConfigPage() {
  const [version, setVersion] = useState(0);
  const bump = () => setVersion((v) => v + 1);
  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8">
        <h1 className="mb-6 font-serif text-xl text-stone-900">Настройки AI</h1>
        <ProvidersSection version={version} onChanged={bump} />
        <ModelsSection version={version} onChanged={bump} />
        <PurposesSection version={version} onChanged={bump} />
        <UsageSection version={version} onChanged={bump} />
        <DadataSettings />
        <YandexSettings />
      </main>
    </div>
  );
}

function YandexSettings() {
  const [clientId, setClientId] = useState("");
  const [hasSecret, setHasSecret] = useState(false);
  const [secret, setSecret] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => {
    void getYandex().then((s) => { setClientId(s.client_id); setHasSecret(s.has_secret); }).catch(() => {});
  }, []);
  async function save() {
    try {
      const s = await setYandex({ client_id: clientId, secret });
      setClientId(s.client_id); setHasSecret(s.has_secret);
      setSecret(""); setMsg("Сохранено");
    } catch (e) { setMsg(e instanceof Error ? e.message : "Ошибка"); }
  }
  return (
    <section className="mt-10">
      <h2 className="mb-2 font-serif text-lg text-stone-900">Интеграции · Яндекс OAuth</h2>
      <p className="mb-2 text-sm text-stone-500">
        Для входа через Яндекс. Redirect URI в Яндекс-приложении:{" "}
        <code className="font-mono">https://smetaapp.ru/api/auth/yandex/callback</code>.
        {" "}Секрет — {hasSecret ? "задан ✓" : "не задан"}. Пустое поле не меняет сохранённое значение.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <input
          type="text"
          aria-label="Client ID Яндекс"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          placeholder="Client ID"
          className="rounded border border-stone-300 px-2 py-1 text-sm"
        />
        <input
          type="password"
          aria-label="Secret Яндекс"
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          placeholder="Секрет (оставьте пустым, чтобы не менять)"
          className="rounded border border-stone-300 px-2 py-1 text-sm"
        />
        <button onClick={() => void save()} className="rounded border border-stone-700 px-3 py-1 text-sm text-stone-700">Сохранить</button>
        {msg && <span className="text-sm text-stone-500">{msg}</span>}
      </div>
    </section>
  );
}

function DadataSettings() {
  const [hasToken, setHasToken] = useState(false);
  const [hasSecret, setHasSecret] = useState(false);
  const [token, setToken] = useState("");
  const [secret, setSecret] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => {
    void getDadataSettings().then((s) => { setHasToken(s.has_token); setHasSecret(s.has_secret); }).catch(() => {});
  }, []);
  async function save() {
    try {
      const s = await saveDadata(token, secret);
      setHasToken(s.has_token); setHasSecret(s.has_secret);
      setToken(""); setSecret(""); setMsg("Сохранено");
    } catch (e) { setMsg(e instanceof Error ? e.message : "Ошибка"); }
  }
  return (
    <section className="mt-10">
      <h2 className="mb-2 font-serif text-lg text-stone-900">Интеграции · DaData</h2>
      <p className="mb-2 text-sm text-stone-500">
        Для автозаполнения реквизитов клиентов. API-ключ — {hasToken ? "задан" : "не задан"}; Secret — {hasSecret ? "задан" : "не задан"}. Пустое поле не меняет сохранённое значение.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <input type="password" aria-label="Ключ DaData" value={token} onChange={(e) => setToken(e.target.value)}
          placeholder="API-ключ" className="rounded border border-stone-300 px-2 py-1 text-sm" />
        <input type="password" aria-label="Secret DaData" value={secret} onChange={(e) => setSecret(e.target.value)}
          placeholder="Secret-ключ" className="rounded border border-stone-300 px-2 py-1 text-sm" />
        <button onClick={() => void save()} className="rounded border border-stone-700 px-3 py-1 text-sm text-stone-700">Сохранить</button>
        {msg && <span className="text-sm text-stone-500">{msg}</span>}
      </div>
    </section>
  );
}
