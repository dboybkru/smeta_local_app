import { ApiError, tryRefresh } from "./client";

export type ExportFormat = "xlsx" | "pdf";
export type ExportLevel = "full" | "cover" | "estimate";

// Бинарное скачивание через cookie-сессию — credentials: "same-origin" достаточно.
function authedFetch(url: string) {
  return fetch(url, { credentials: "same-origin" });
}

export async function downloadExport(
  estimateId: number,
  fmt: ExportFormat,
  level: ExportLevel,
): Promise<void> {
  const endpoint = `/api/estimates/${estimateId}/export.${fmt}?level=${level}`;
  let resp = await authedFetch(endpoint);
  if (resp.status === 401 && (await tryRefresh())) {
    resp = await authedFetch(endpoint); // повтор после обновления токена
  }
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
