import type { Column, ColumnMapping, PriceLevel } from "../api/catalog";

type Props = {
  columns: Column[];
  levels: PriceLevel[];
  mapping: ColumnMapping;
  onChange: (mapping: ColumnMapping) => void;
};

// "" in a <select> means "not mapped" → null (or removed from price_cols).
function parseCol(value: string): number | null {
  return value === "" ? null : Number(value);
}

export default function ColumnMapper({ columns, levels, mapping, onChange }: Props) {
  const options = (
    <>
      <option value="">—</option>
      {columns.map((c) => (
        <option key={c.index} value={c.index}>{c.header}</option>
      ))}
    </>
  );

  function setField(field: "name_col" | "article_col" | "unit_col" | "category_col" | "characteristics_col", value: string) {
    const col = parseCol(value);
    // name_col is required — fall back to the first column if cleared.
    onChange({ ...mapping, [field]: field === "name_col" ? (col ?? 0) : col });
  }

  function setPriceCol(levelId: number, value: string) {
    const next = { ...mapping.price_cols };
    const col = parseCol(value);
    if (col === null) delete next[levelId];
    else next[levelId] = col;
    onChange({ ...mapping, price_cols: next });
  }

  const nameSamples = columns.find((c) => c.index === mapping.name_col)?.samples ?? [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <label className="block">
          <span className="mb-1 block text-stone-600">Наименование</span>
          <select
            aria-label="Наименование"
            value={mapping.name_col}
            onChange={(e) => setField("name_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-stone-600">Артикул</span>
          <select
            aria-label="Артикул"
            value={mapping.article_col ?? ""}
            onChange={(e) => setField("article_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-stone-600">Единица</span>
          <select
            aria-label="Единица"
            value={mapping.unit_col ?? ""}
            onChange={(e) => setField("unit_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-stone-600">Категория</span>
          <select
            aria-label="Категория"
            value={mapping.category_col ?? ""}
            onChange={(e) => setField("category_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-stone-600">Характеристики</span>
          <select
            aria-label="Характеристики"
            value={mapping.characteristics_col ?? ""}
            onChange={(e) => setField("characteristics_col", e.target.value)}
            className="w-full rounded border border-stone-300 px-2 py-1"
          >
            {options}
          </select>
        </label>
      </div>

      {nameSamples.length > 0 && (
        <p className="text-xs text-stone-400">
          Пример наименований: {nameSamples.slice(0, 3).join(", ")}
        </p>
      )}

      <div>
        <h3 className="mb-2 font-serif text-stone-800">Цены по уровням</h3>
        {levels.length === 0 && (
          <p className="text-sm text-stone-500">
            Нет уровней цен. Сначала создайте их на странице «Уровни цен».
          </p>
        )}
        <div className="grid grid-cols-2 gap-4 text-sm">
          {levels.map((l) => (
            <label key={l.id} className="block">
              <span className="mb-1 block text-stone-600">Цена: {l.name}</span>
              <select
                aria-label={`Цена: ${l.name}`}
                value={mapping.price_cols[l.id] ?? ""}
                onChange={(e) => setPriceCol(l.id, e.target.value)}
                className="w-full rounded border border-stone-300 px-2 py-1"
              >
                {options}
              </select>
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
