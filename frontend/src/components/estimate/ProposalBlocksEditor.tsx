import { useState } from "react";
import type { ProposalBlocks } from "../../api/proposals";

type Props = {
  blocks: ProposalBlocks;
  canEdit: boolean;
  onField: (key: keyof ProposalBlocks, value: string) => void;
  onAdvantages: (items: string[]) => void;
};

const TEXT_FIELDS: { key: keyof ProposalBlocks; label: string; area?: boolean }[] = [
  { key: "title", label: "Заголовок" },
  { key: "subtitle", label: "Подзаголовок" },
  { key: "pain", label: "Боль клиента", area: true },
  { key: "solution", label: "Решение / результат", area: true },
  { key: "terms", label: "Условия", area: true },
  { key: "cta", label: "Призыв к действию" },
];

export default function ProposalBlocksEditor({ blocks, canEdit, onField, onAdvantages }: Props) {
  return (
    <div className="grid max-w-2xl gap-4">
      {TEXT_FIELDS.map(({ key, label, area }) => (
        <label key={key} className="grid gap-1 text-sm">
          <span className="text-stone-500">{label}</span>
          {area ? (
            <textarea
              aria-label={label}
              defaultValue={blocks[key] as string}
              disabled={!canEdit}
              rows={3}
              onBlur={(e) => onField(key, e.target.value)}
              className="rounded border border-stone-300 px-2 py-1 disabled:bg-stone-100"
            />
          ) : (
            <input
              aria-label={label}
              defaultValue={blocks[key] as string}
              disabled={!canEdit}
              onBlur={(e) => onField(key, e.target.value)}
              className="rounded border border-stone-300 px-2 py-1 disabled:bg-stone-100"
            />
          )}
        </label>
      ))}
      <AdvantagesEditor items={blocks.advantages} canEdit={canEdit} onChange={onAdvantages} />
    </div>
  );
}

function AdvantagesEditor({ items, canEdit, onChange }: { items: string[]; canEdit: boolean; onChange: (v: string[]) => void }) {
  return (
    <div className="grid gap-1 text-sm">
      <span className="text-stone-500">Преимущества</span>
      <div className="flex flex-wrap gap-2">
        {items.map((it, i) => (
          <span key={i} className="flex items-center gap-1 rounded-full bg-stone-200 px-3 py-0.5">
            {it}
            {canEdit && (
              <button aria-label={`Удалить преимущество ${it}`} onClick={() => onChange(items.filter((_, j) => j !== i))}>✕</button>
            )}
          </span>
        ))}
      </div>
      {canEdit && <AddAdvantage onAdd={(v) => onChange([...items, v])} />}
    </div>
  );
}

function AddAdvantage({ onAdd }: { onAdd: (v: string) => void }) {
  const [draft, setDraft] = useState("");
  return (
    <div className="flex gap-2">
      <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Новое преимущество"
        className="rounded border border-stone-300 px-2 py-1" />
      <button onClick={() => { if (draft.trim()) { onAdd(draft.trim()); setDraft(""); } }}
        className="rounded border border-stone-700 px-3 py-1 text-stone-700">+ преимущество</button>
    </div>
  );
}
