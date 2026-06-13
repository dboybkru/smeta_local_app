import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import EstimateHeader from "../components/estimate/EstimateHeader";
import EstimateTotalsBar from "../components/estimate/EstimateTotalsBar";
import SectionTable from "../components/estimate/SectionTable";
import { listClients, createClient, type Client } from "../api/estimates";
import { useEstimate } from "../hooks/useEstimate";

export default function EstimateEditorPage() {
  const { id } = useParams();
  const estimateId = Number(id);
  const e = useEstimate(estimateId);
  const [clients, setClients] = useState<Client[]>([]);
  const [newSection, setNewSection] = useState("");

  useEffect(() => {
    listClients().then(setClients).catch(() => setClients([]));
  }, []);

  if (e.loading) return <Shell><p className="text-stone-500">Загрузка…</p></Shell>;
  // Полноэкранная ошибка — только если смета не загрузилась. Ошибки мутаций
  // (e.error при загруженной смете) показываются внутренним alert, не стирая редактор.
  if (!e.estimate) {
    return <Shell><p role="alert" className="text-red-600">{e.error || "Смета не найдена"}</p></Shell>;
  }

  const est = e.estimate;
  const totals = est.totals;
  const showMargin = totals.margin != null;
  const sections = est.branches[0]?.sections ?? [];
  const sectionTotals = (sid: number) => totals.sections.find((s) => s.section_id === sid);

  async function handleCreateClient(name: string) {
    try {
      const client = await createClient(name);
      setClients((cs) => [...cs, client]);
      await e.patchEstimate({ client_id: client.id });
    } catch {
      // ошибка patch/создания отразится через e.error при следующем reload; молча не критично
    }
  }

  return (
    <Shell>
      {e.error && <p role="alert" className="mb-3 text-red-600">{e.error}</p>}
      <EstimateHeader key={est.id} estimate={est} clients={clients} canEdit={e.canEdit} onPatch={e.patchEstimate} onCreateClient={handleCreateClient} />

      {sections.map((s) => (
        <SectionTable
          key={s.id}
          section={s}
          totals={sectionTotals(s.id)}
          canEdit={e.canEdit}
          showMargin={showMargin}
          onAddLine={(body) => e.addLine(s.id, body)}
          onPatchLine={(lid, patch) => e.patchLine(lid, patch)}
          onDeleteLine={(lid) => e.deleteLine(lid)}
          onPatchSection={(patch) => e.patchSection(s.id, patch)}
          onDeleteSection={() => e.deleteSection(s.id)}
        />
      ))}

      {e.canEdit && (
        <div className="mb-6 flex items-center gap-2 text-sm">
          <input
            value={newSection}
            onChange={(ev) => setNewSection(ev.target.value)}
            placeholder="Новый раздел"
            className="rounded border border-stone-300 px-2 py-1"
          />
          <button
            onClick={() => { if (newSection.trim()) { void e.addSection({ name: newSection.trim() }); setNewSection(""); } }}
            className="rounded border border-stone-700 px-3 py-1 text-stone-700"
          >
            + раздел
          </button>
        </div>
      )}

      <EstimateTotalsBar totals={totals} vatEnabled={est.vat_enabled} />
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="mx-auto max-w-4xl p-8">{children}</main>
    </div>
  );
}
