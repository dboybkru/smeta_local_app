import { useState } from "react";
import type { CatalogItem } from "../../api/catalog";
import type { LineCreate, LineDetail, LinePatch, SectionDetail, SectionTotals } from "../../api/estimates";
import { fmtMoney } from "../../lib/format";
import CatalogSearchInput from "./CatalogSearchInput";

type Props = {
  section: SectionDetail;
  totals: SectionTotals | undefined;
  canEdit: boolean;
  showMargin: boolean;
  onAddLine: (body: LineCreate) => void;
  onPatchLine: (id: number, patch: LinePatch) => void;
  onDeleteLine: (id: number) => void;
  onPatchSection: (patch: Partial<{ name: string; markup_percent: string }>) => void;
  onDeleteSection: () => void;
};

function lineSum(l: LineDetail): string {
  return ((Number(l.work_price) + Number(l.material_price)) * Number(l.qty)).toString();
}

export default function SectionTable({
  section, totals, canEdit, showMargin,
  onAddLine, onPatchLine, onDeleteLine, onPatchSection, onDeleteSection,
}: Props) {
  const [name, setName] = useState(section.name);
  const [markup, setMarkup] = useState(section.markup_percent);
  const [freeform, setFreeform] = useState(false);

  function pick(item: CatalogItem) {
    onAddLine({ item_id: item.id, qty: "1" });
  }

  const colCount = 4 + (showMargin ? 1 : 0) + (canEdit ? 1 : 0);

  return (
    <div className="mb-6">
      <div className="mb-1 flex items-center gap-2">
        <input
          value={name}
          disabled={!canEdit}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => name !== section.name && onPatchSection({ name })}
          className="rounded border border-stone-300 px-2 py-1 font-serif text-stone-800 disabled:border-transparent disabled:bg-transparent"
        />
        {canEdit && (
          <label className="flex items-center gap-1 text-xs text-stone-500">
            наценка %
            <input
              value={markup}
              onChange={(e) => setMarkup(e.target.value)}
              onBlur={() => markup !== section.markup_percent && onPatchSection({ markup_percent: markup })}
              className="w-16 rounded border border-stone-300 px-2 py-1"
            />
          </label>
        )}
        {canEdit && (
          <button onClick={onDeleteSection} className="ml-auto text-xs text-red-700">удалить раздел</button>
        )}
      </div>

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-stone-300 text-left text-stone-500">
            <th className="py-1">Наименование</th>
            <th className="w-20 text-right">Кол-во</th>
            <th className="w-24 text-right">Цена</th>
            <th className="w-28 text-right">Сумма</th>
            {showMargin && <th className="w-24 text-right">Маржа</th>}
            {canEdit && <th className="w-8" />}
          </tr>
        </thead>
        <tbody>
          {section.lines.map((l) => {
            const price = (Number(l.work_price) + Number(l.material_price)).toString();
            return (
              <tr key={l.id} className="border-b border-stone-100">
                <td className="py-1 text-stone-800">{l.name}</td>
                <td className="text-right">
                  <input
                    aria-label={`Количество строки ${l.id}`}
                    defaultValue={l.qty}
                    disabled={!canEdit}
                    onBlur={(e) => e.target.value !== l.qty && onPatchLine(l.id, { qty: e.target.value })}
                    className="w-16 rounded border border-stone-200 px-1 py-0.5 text-right tabular-nums disabled:border-transparent"
                  />
                </td>
                <td className="text-right tabular-nums text-stone-500">{fmtMoney(price)}</td>
                <td className="text-right tabular-nums">{fmtMoney(lineSum(l))}</td>
                {showMargin && (
                  <td className="text-right tabular-nums text-green-700">
                    {l.purchase_price_snapshot != null
                      ? fmtMoney((((Number(l.work_price) + Number(l.material_price)) - Number(l.purchase_price_snapshot)) * Number(l.qty)).toString())
                      : "—"}
                  </td>
                )}
                {canEdit && (
                  <td className="text-right">
                    <button onClick={() => onDeleteLine(l.id)} className="text-red-700">×</button>
                  </td>
                )}
              </tr>
            );
          })}

          {canEdit && (
            <tr>
              <td colSpan={colCount} className="py-2">
                {!freeform ? (
                  <div className="flex items-center gap-2">
                    <div className="flex-1"><CatalogSearchInput onPick={pick} /></div>
                    <button onClick={() => setFreeform(true)} className="text-xs text-stone-500">своя строка</button>
                  </div>
                ) : (
                  <FreeformRow onAdd={(body) => { onAddLine(body); setFreeform(false); }} onCancel={() => setFreeform(false)} />
                )}
              </td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-stone-300 font-medium">
            <td className="py-1" colSpan={3}>Итого по разделу</td>
            <td className="text-right tabular-nums">{fmtMoney(totals?.total)}</td>
            {showMargin && <td className="text-right tabular-nums text-green-700">{fmtMoney(totals?.margin)}</td>}
            {canEdit && <td />}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function FreeformRow({ onAdd, onCancel }: { onAdd: (b: LineCreate) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("шт");
  const [price, setPrice] = useState("");
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Наименование" className="flex-1 rounded border border-stone-300 px-2 py-1" />
      <input value={unit} onChange={(e) => setUnit(e.target.value)} className="w-16 rounded border border-stone-300 px-2 py-1" />
      <input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="цена" className="w-24 rounded border border-stone-300 px-2 py-1" />
      <button
        onClick={() => name.trim() && onAdd({ name: name.trim(), unit, qty: "1", material_price: price || "0" })}
        className="rounded border border-stone-700 px-2 py-1 text-stone-700"
      >
        Добавить
      </button>
      <button onClick={onCancel} className="text-xs text-stone-500">отмена</button>
    </div>
  );
}
