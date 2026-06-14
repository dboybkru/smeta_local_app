import { useState } from "react";
import { ApiError } from "../../api/client";
import { generateProposal, patchProposal, type ProposalBlocks } from "../../api/proposals";
import ProposalBlocksEditor from "./ProposalBlocksEditor";

const EMPTY: ProposalBlocks = { title: "", subtitle: "", pain: "", solution: "", advantages: [], terms: "", cta: "" };

// Защита от кривых данных (AI/частичный PATCH мог вернуть неполную форму) —
// иначе .map по advantages роняет всю вкладку в белый экран.
function normalize(b: Partial<ProposalBlocks> | null | undefined): ProposalBlocks {
  return {
    title: b?.title ?? "",
    subtitle: b?.subtitle ?? "",
    pain: b?.pain ?? "",
    solution: b?.solution ?? "",
    advantages: Array.isArray(b?.advantages) ? b!.advantages : [],
    terms: b?.terms ?? "",
    cta: b?.cta ?? "",
  };
}

export default function ProposalTab({
  estimateId, initial, canEdit, onSaved,
}: {
  estimateId: number;
  initial: ProposalBlocks | null;
  canEdit: boolean;
  onSaved?: () => void;  // обновить родителя (est.proposal), чтобы не терялось при смене вкладки
}) {
  const [blocks, setBlocks] = useState<ProposalBlocks>(initial ? normalize(initial) : EMPTY);
  const [hasBlocks, setHasBlocks] = useState<boolean>(initial != null);
  const [rev, setRev] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notConfigured, setNotConfigured] = useState(false);
  const [error, setError] = useState("");

  async function generate() {
    if (hasBlocks && !window.confirm("Перезаписать существующие блоки КП?")) return;
    setBusy(true); setError(""); setNotConfigured(false);
    try {
      const out = await generateProposal(estimateId);
      setBlocks(normalize(out)); setHasBlocks(true); setRev((r) => r + 1);
      onSaved?.();
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) setNotConfigured(true);
      else setError(e instanceof Error ? e.message : "Ошибка генерации");
    } finally {
      setBusy(false);
    }
  }

  async function saveField(key: keyof ProposalBlocks, value: string) {
    if ((blocks[key] as string) === value) return;
    try {
      const out = await patchProposal(estimateId, { [key]: value });
      setBlocks(normalize(out)); setHasBlocks(true);
      onSaved?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    }
  }

  async function saveAdvantages(items: string[]) {
    setBlocks((b) => ({ ...b, advantages: items }));
    try {
      const out = await patchProposal(estimateId, { advantages: items });
      setBlocks(normalize(out)); setHasBlocks(true);
      onSaved?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    }
  }

  return (
    <div>
      {notConfigured && (
        <div className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          ⚠ AI не настроен — заполните блоки вручную или попросите администратора подключить провайдера.
        </div>
      )}
      {error && <p role="alert" className="mb-3 text-red-600 text-sm">{error}</p>}
      {canEdit && (
        <div className="mb-4 flex items-center gap-3">
          <button onClick={generate} disabled={busy}
            className="rounded border border-stone-700 px-4 py-1.5 text-stone-700 disabled:opacity-50">
            {busy ? "Генерация…" : "✨ Сгенерировать AI"}
          </button>
          <span className="text-xs text-stone-400">перезапишет все блоки · сохраняется автоматически</span>
        </div>
      )}
      <ProposalBlocksEditor key={rev} blocks={blocks} canEdit={canEdit} onField={saveField} onAdvantages={saveAdvantages} />
    </div>
  );
}
