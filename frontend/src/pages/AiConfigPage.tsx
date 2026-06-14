import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import ProvidersSection from "../components/ai/ProvidersSection";
import ModelsSection from "../components/ai/ModelsSection";
import PurposesSection from "../components/ai/PurposesSection";
import UsageSection from "../components/ai/UsageSection";
import { getDadataSettings, setDadataToken } from "../api/settings";

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
      </main>
    </div>
  );
}

function DadataSettings() {
  const [hasToken, setHasToken] = useState(false);
  const [token, setToken] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => { void getDadataSettings().then((s) => setHasToken(s.has_token)).catch(() => {}); }, []);
  async function save() {
    try { const s = await setDadataToken(token); setHasToken(s.has_token); setToken(""); setMsg("Сохранено"); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Ошибка"); }
  }
  return (
    <section className="mt-10">
      <h2 className="mb-2 font-serif text-lg text-stone-900">Интеграции · DaData</h2>
      <p className="mb-2 text-sm text-stone-500">Ключ для автозаполнения реквизитов клиентов. {hasToken ? "Ключ задан." : "Ключ не задан."}</p>
      <div className="flex items-end gap-2">
        <input type="password" aria-label="Ключ DaData" value={token} onChange={(e) => setToken(e.target.value)}
          placeholder="API-ключ DaData" className="rounded border border-stone-300 px-2 py-1 text-sm" />
        <button onClick={() => void save()} className="rounded border border-stone-700 px-3 py-1 text-sm text-stone-700">Сохранить</button>
        {msg && <span className="text-sm text-stone-500">{msg}</span>}
      </div>
    </section>
  );
}
