import { api } from "./client";

export type Job = {
  id: number;
  type: string;
  status: "pending" | "running" | "done" | "error";
  processed: number;
  total: number | null;
  message: string;
  error: string;
};

export function startCatalogExtract(supplierId?: number, force = false) {
  const p = new URLSearchParams();
  if (supplierId != null) p.set("supplier_id", String(supplierId));
  if (force) p.set("force", "true");
  const qs = p.toString();
  return api<Job>(`/catalog/extract-characteristics/start${qs ? `?${qs}` : ""}`, { method: "POST" });
}

export function getJob(id: number) {
  return api<Job>(`/jobs/${id}`);
}
