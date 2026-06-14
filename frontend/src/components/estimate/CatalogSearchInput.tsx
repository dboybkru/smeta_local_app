import { useEffect, useRef, useState } from "react";
import { listItems, type CatalogItem } from "../../api/catalog";
import { fmtMoney } from "../../lib/format";

type Props = { onPick: (item: CatalogItem) => void };

export default function CatalogSearchInput({ onPick }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<CatalogItem[]>([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    const handle = setTimeout(() => {
      listItems({ q, limit: 30 })
        .then((page) => {
          setResults(page.items);
          setOpen(true);
        })
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(handle);
  }, [q]);

  function pick(item: CatalogItem) {
    onPick(item);
    setQ("");
    setResults([]);
    setOpen(false);
  }

  const firstPrice = (it: CatalogItem) => {
    const vals = Object.values(it.prices);
    return vals.length ? fmtMoney(vals[0]) : "—";
  };

  return (
    <div ref={boxRef} className="relative">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
        placeholder="Поиск позиции в каталоге…"
        className="w-full rounded border border-stone-300 px-2 py-1 text-sm"
      />
      {open && results.length > 0 && (
        <div className="absolute z-10 mt-1 max-h-96 w-full overflow-y-auto overscroll-contain rounded border border-stone-300 bg-white shadow-lg">
          {results.map((it) => (
            <button
              key={it.id}
              type="button"
              onClick={() => pick(it)}
              className="flex w-full items-center justify-between border-b border-stone-100 px-2 py-1 text-left text-sm hover:bg-stone-100"
            >
              <span className="text-stone-800">{it.name}</span>
              <span className="ml-2 shrink-0 tabular-nums text-stone-500">{firstPrice(it)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
