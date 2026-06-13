import { ApiError, getTokens } from "./client";

export type ExportFormat = "xlsx" | "pdf";
export type ExportLevel = "full" | "cover" | "estimate";

// Бинарное скачивание: нужен заголовок Authorization, поэтому не api() (тот делает .json()).
export async function downloadExport(
  estimateId: number,
  fmt: ExportFormat,
  level: ExportLevel,
): Promise<void> {
  const { access } = getTokens();
  const resp = await fetch(`/api/estimates/${estimateId}/export.${fmt}?level=${level}`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  });
  if (!resp.ok) throw new ApiError(resp.status, resp.statusText);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `estimate-${estimateId}.${fmt}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
