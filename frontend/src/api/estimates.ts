import { api } from "./client";
import type { ProposalBlocks } from "./proposals";

// Money & qty are JSON strings (backend Decimal).
export type Branch = { id: number; name: string; parent_branch_id: number | null };

export type Estimate = {
  id: number;
  client_id: number | null;
  owner_id: number;
  object_name: string;
  status: string;
  vat_enabled: boolean;
  vat_rate: string;
  branches: Branch[];
};

export type LineDetail = {
  id: number;
  section_id: number;
  item_id: number | null;
  name: string;
  unit: string;
  qty: string;
  work_price: string;
  material_price: string;
  sort_order: number;
  purchase_price_snapshot: string | null;
};
export type SectionDetail = {
  id: number;
  name: string;
  sort_order: number;
  markup_percent: string;
  lines: LineDetail[];
};
export type BranchDetail = { id: number; name: string; sections: SectionDetail[] };

export type SectionTotals = {
  section_id: number;
  materials: string;
  works: string;
  total: string;
  purchase: string | null;
  margin: string | null;
};
export type EstimateTotals = {
  sections: SectionTotals[];
  materials: string;
  works: string;
  subtotal: string;
  vat: string;
  total: string;
  purchase: string | null;
  margin: string | null;
};
export type EstimateDetail = Omit<Estimate, "branches"> & {
  branches: BranchDetail[];
  totals: EstimateTotals;
  proposal: ProposalBlocks | null;
};

export type Client = {
  id: number;
  name: string;
  default_price_level_id: number | null;
  created_at: string;
};

export type EstimateCreate = {
  object_name: string;
  client_id?: number | null;
  vat_enabled?: boolean;
  vat_rate?: string;
};
export type EstimatePatch = Partial<{
  object_name: string;
  status: string;
  client_id: number | null;
  vat_enabled: boolean;
  vat_rate: string;
}>;
export type LineCreate = {
  item_id?: number;
  name?: string;
  unit?: string;
  qty: string;
  work_price?: string;
  material_price?: string;
  purchase_price_snapshot?: string;
};
export type LinePatch = Partial<{
  name: string;
  unit: string;
  qty: string;
  work_price: string;
  material_price: string;
  sort_order: number;
  purchase_price_snapshot: string;
}>;

const j = (body: unknown) => JSON.stringify(body);

// estimates
export const listEstimates = () => api<Estimate[]>("/estimates");
export const createEstimate = (body: EstimateCreate) =>
  api<Estimate>("/estimates", { method: "POST", body: j(body) });
export const getEstimate = (id: number) => api<EstimateDetail>(`/estimates/${id}`);
export const patchEstimate = (id: number, patch: EstimatePatch) =>
  api<Estimate>(`/estimates/${id}`, { method: "PATCH", body: j(patch) });
export const deleteEstimate = (id: number) =>
  api<void>(`/estimates/${id}`, { method: "DELETE" });

// sections
export const addSection = (estimateId: number, body: { name?: string; markup_percent?: string }) =>
  api<SectionDetail>(`/estimates/${estimateId}/sections`, { method: "POST", body: j(body) });
export const patchSection = (
  id: number,
  patch: Partial<{ name: string; sort_order: number; markup_percent: string }>,
) => api<SectionDetail>(`/sections/${id}`, { method: "PATCH", body: j(patch) });
export const deleteSection = (id: number) =>
  api<void>(`/sections/${id}`, { method: "DELETE" });

// lines
export const addLine = (sectionId: number, body: LineCreate) =>
  api<LineDetail>(`/sections/${sectionId}/lines`, { method: "POST", body: j(body) });
export const patchLine = (id: number, patch: LinePatch) =>
  api<LineDetail>(`/lines/${id}`, { method: "PATCH", body: j(patch) });
export const deleteLine = (id: number) => api<void>(`/lines/${id}`, { method: "DELETE" });

// clients
export const listClients = () => api<Client[]>("/clients");
export const createClient = (name: string, default_price_level_id?: number | null) =>
  api<Client>("/clients", { method: "POST", body: j({ name, default_price_level_id }) });
