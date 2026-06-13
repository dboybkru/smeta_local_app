import { useState } from "react";
import type { Client, EstimateDetail, EstimatePatch } from "../../api/estimates";

type Props = {
  estimate: EstimateDetail;
  clients: Client[];
  canEdit: boolean;
  onPatch: (patch: EstimatePatch) => void;
};

const STATUSES = ["draft", "sent", "approved", "archived"];

export default function EstimateHeader({ estimate, clients, canEdit, onPatch }: Props) {
  const [name, setName] = useState(estimate.object_name);

  return (
    <div className="mb-6 space-y-3">
      <input
        value={name}
        disabled={!canEdit}
        onChange={(e) => setName(e.target.value)}
        onBlur={() => name !== estimate.object_name && onPatch({ object_name: name })}
        className="w-full rounded border border-stone-300 px-2 py-1 font-serif text-xl text-stone-900 disabled:border-transparent disabled:bg-transparent"
        placeholder="Название объекта"
      />
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <label className="flex items-center gap-1">
          <span className="text-stone-500">Клиент</span>
          <select
            aria-label="Клиент"
            disabled={!canEdit}
            value={estimate.client_id ?? ""}
            onChange={(e) => onPatch({ client_id: e.target.value === "" ? null : Number(e.target.value) })}
            className="rounded border border-stone-300 px-2 py-1"
          >
            <option value="">—</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            aria-label="НДС"
            disabled={!canEdit}
            checked={estimate.vat_enabled}
            onChange={(e) => onPatch({ vat_enabled: e.target.checked })}
          />
          НДС
        </label>
        {estimate.vat_enabled && (
          <label className="flex items-center gap-1">
            <span className="text-stone-500">Ставка %</span>
            <input
              aria-label="Ставка НДС"
              disabled={!canEdit}
              defaultValue={estimate.vat_rate}
              onBlur={(e) => e.target.value !== estimate.vat_rate && onPatch({ vat_rate: e.target.value })}
              className="w-16 rounded border border-stone-300 px-2 py-1"
            />
          </label>
        )}
        <label className="flex items-center gap-1">
          <span className="text-stone-500">Статус</span>
          <select
            aria-label="Статус"
            disabled={!canEdit}
            value={estimate.status}
            onChange={(e) => onPatch({ status: e.target.value })}
            className="rounded border border-stone-300 px-2 py-1"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
