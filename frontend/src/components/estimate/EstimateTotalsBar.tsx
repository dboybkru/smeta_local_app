import type { EstimateTotals } from "../../api/estimates";
import { fmtMoney } from "../../lib/format";

type Props = { totals: EstimateTotals; vatEnabled: boolean };

export default function EstimateTotalsBar({ totals, vatEnabled }: Props) {
  return (
    <div className="sticky bottom-0 mt-6 flex flex-wrap items-center justify-end gap-x-6 gap-y-1 border-t border-stone-300 bg-white/95 px-6 py-3 text-sm">
      <span className="text-stone-500">
        Материалы <span>{fmtMoney(totals.materials)}</span>
      </span>
      <span className="text-stone-500">
        Работы <span>{fmtMoney(totals.works)}</span>
      </span>
      <span className="text-stone-600">
        Без НДС <span>{fmtMoney(totals.subtotal)}</span>
      </span>
      {vatEnabled && (
        <span className="text-stone-600">
          НДС <span>{fmtMoney(totals.vat)}</span>
        </span>
      )}
      <span className="font-serif text-lg text-stone-900">
        Всего <span>{fmtMoney(totals.total)}</span>
      </span>
      {totals.margin != null && (
        <span className="text-green-700">
          Маржа <span>{fmtMoney(totals.margin)}</span>
        </span>
      )}
    </div>
  );
}
