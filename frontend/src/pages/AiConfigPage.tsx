import { useState } from "react";
import AppHeader from "../components/AppHeader";
import ProvidersSection from "../components/ai/ProvidersSection";
import ModelsSection from "../components/ai/ModelsSection";
import PurposesSection from "../components/ai/PurposesSection";
import UsageSection from "../components/ai/UsageSection";

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
      </main>
    </div>
  );
}
