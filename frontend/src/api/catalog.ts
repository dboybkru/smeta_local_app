import { api, apiUpload } from "./client";

export type PriceLevel = { id: number; name: string; sort_order: number };

export type ColumnMapping = {
  name_col: number;
  article_col: number | null;
  unit_col: number | null;
  category_col: number | null;
  characteristics_col: number | null;
  manufacturer_col?: number | null;
  header_row?: number;
  data_start_row?: number | null;
  price_cols: Record<number, number>; // price_level_id -> column index
  on_request_cols?: number[];
};

export type PriceColumn = {
  index: number;
  label: string;
  sample: string;
  on_request: boolean;
};

export type DetectedLayout = {
  header_row: number;
  data_start_row: number;
  name_col: number | null;
  article_col: number | null;
  chars_col: number | null;
  unit_col: number | null;
  manufacturer_col: number | null;
  price_columns: PriceColumn[];
  confidence: number;
};

export type Supplier = { id: number; name: string; column_mapping_template: ColumnMapping | null };

export type Column = { index: number; header: string; samples: string[] };
export type Sheet = { name: string; row_count: number; header_row: number; columns: Column[]; detected: DetectedLayout | null };
export type InspectResult = { sheets: Sheet[] };

export type ImportSummary = {
  price_list_id: number;
  version: number;
  items_created: number;
  items_updated: number;
  prices_written: number;
  price_changes: number;
  rows_skipped: number;
  problems: string[];
};

export type CatalogItem = {
  id: number;
  supplier_id: number;
  name: string;
  article: string;
  unit: string;
  category: string;
  kind: string;
  manufacturer: string | null;
  price_on_request: boolean;
  prices: Record<string, string>; // level_id (string) -> decimal string
  characteristics: Record<string, string> | null;
};
export type ItemsPage = { items: CatalogItem[]; total: number };

export type PriceList = {
  id: number;
  supplier_id: number;
  filename: string;
  version: number;
  imported_at: string | null;
};

// --- price levels ---
export const listPriceLevels = () => api<PriceLevel[]>("/price-levels");
export const createPriceLevel = (name: string, sort_order: number) =>
  api<PriceLevel>("/price-levels", { method: "POST", body: JSON.stringify({ name, sort_order }) });
export const updatePriceLevel = (id: number, patch: { name?: string; sort_order?: number }) =>
  api<PriceLevel>(`/price-levels/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
export const deletePriceLevel = (id: number) =>
  api<void>(`/price-levels/${id}`, { method: "DELETE" });

// --- suppliers ---
export const listSuppliers = () => api<Supplier[]>("/suppliers");
export const createSupplier = (name: string) =>
  api<Supplier>("/suppliers", { method: "POST", body: JSON.stringify({ name }) });

// --- import ---
export const inspectFile = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return apiUpload<InspectResult>("/catalog/inspect", form);
};

export type ImportSheetMapping = { name: string; mapping: ColumnMapping };

export type ImportParams = {
  file: File;
  supplier_id: number;
  kind: "material" | "work";
  sheet_mappings: ImportSheetMapping[];
  use_sheet_as_category: boolean;
  save_mapping: boolean;
};
export const importFile = (p: ImportParams) => {
  const form = new FormData();
  form.append("file", p.file);
  form.append("supplier_id", String(p.supplier_id));
  form.append("kind", p.kind);
  form.append("sheet_mappings", JSON.stringify(p.sheet_mappings));
  form.append("use_sheet_as_category", String(p.use_sheet_as_category));
  form.append("save_mapping", String(p.save_mapping));
  return apiUpload<ImportSummary>("/catalog/import", form);
};

// --- catalog browse ---
export type ItemFilters = {
  q?: string;
  supplier_id?: number;
  kind?: string;
  limit?: number;
  offset?: number;
  facets?: Record<string, string>;
};
export const listItems = (f: ItemFilters = {}) => {
  const params = new URLSearchParams();
  if (f.q) params.set("q", f.q);
  if (f.supplier_id != null) params.set("supplier_id", String(f.supplier_id));
  if (f.kind) params.set("kind", f.kind);
  if (f.limit != null) params.set("limit", String(f.limit));
  if (f.offset != null) params.set("offset", String(f.offset));
  for (const [k, v] of Object.entries(f.facets ?? {})) params.append("f", `${k}=${v}`);
  return api<ItemsPage>(`/catalog/items?${params.toString()}`);
};

export const clearCatalog = (supplierId?: number) => {
  const q = supplierId != null ? `?supplier_id=${supplierId}` : "";
  return api<{ deleted: number }>(`/catalog/items${q}`, { method: "DELETE" });
};

export const getFacets = (supplierId?: number, kind?: string) => {
  const p = new URLSearchParams();
  if (supplierId != null) p.set("supplier_id", String(supplierId));
  if (kind) p.set("kind", kind);
  const qs = p.toString();
  return api<Record<string, string[]>>(`/catalog/facets${qs ? `?${qs}` : ""}`);
};

export const extractCharacteristics = (supplierId?: number, batch = 40) => {
  const params = new URLSearchParams({ batch: String(batch) });
  if (supplierId != null) params.set("supplier_id", String(supplierId));
  return api<{ processed: number; remaining: number }>(
    `/catalog/extract-characteristics?${params.toString()}`,
    { method: "POST" },
  );
};

export const listPriceLists = (supplier_id?: number) => {
  const params = new URLSearchParams();
  if (supplier_id != null) params.set("supplier_id", String(supplier_id));
  const qs = params.toString();
  return api<PriceList[]>(`/catalog/price-lists${qs ? `?${qs}` : ""}`);
};
