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

export function startCatalogExtract(supplierId?: number) {
  const q = supplierId != null ? `?supplier_id=${supplierId}` : "";
  return api<Job>(`/catalog/extract-characteristics/start${q}`, { method: "POST" });
}

export function getJob(id: number) {
  return api<Job>(`/jobs/${id}`);
}
