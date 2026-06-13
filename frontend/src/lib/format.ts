// Decimal string "1234.5" → "1 234,50" (ru-RU). null/"" → "—".
export function fmtMoney(value: string | null | undefined): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return n.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
