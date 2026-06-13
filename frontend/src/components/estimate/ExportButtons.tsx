import { useState } from "react";
import { downloadExport, type ExportLevel } from "../../api/export";

const LEVELS: { value: ExportLevel; label: string }[] = [
  { value: "full", label: "Полное КП" },
  { value: "cover", label: "Титул + смета" },
  { value: "estimate", label: "Только смета" },
];

export default function ExportButtons({ estimateId }: { estimateId: number }) {
  const [level, setLevel] = useState<ExportLevel>("full");
  const [error, setError] = useState("");

  async function dl(fmt: "xlsx" | "pdf") {
    setError("");
    try {
      await downloadExport(estimateId, fmt, level);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка скачивания");
    }
  }

  return (
    <div className="grid gap-2 text-sm">
      <label className="grid max-w-xs gap-1">
        <span className="text-stone-500">Уровень</span>
        <select aria-label="Уровень" value={level} onChange={(e) => setLevel(e.target.value as ExportLevel)}
          className="rounded border border-stone-300 px-2 py-1">
          {LEVELS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
        </select>
      </label>
      <div className="flex gap-2">
        <button onClick={() => dl("xlsx")} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Скачать Excel</button>
        <button onClick={() => dl("pdf")} className="rounded border border-stone-700 px-3 py-1 text-stone-700">Скачать PDF</button>
      </div>
      {error && <p role="alert" className="text-red-600">{error}</p>}
    </div>
  );
}
