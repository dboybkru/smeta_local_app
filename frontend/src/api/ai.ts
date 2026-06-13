import { api } from "./client";

export type AuthStyle = "bearer" | "x_api_key";

export type Provider = {
  id: number;
  name: string;
  base_url: string;
  auth_style: AuthStyle;
  enabled: boolean;
  has_key: boolean;
};

export type ProviderCreate = {
  name: string;
  base_url: string;
  auth_style: AuthStyle;
  api_key: string;
  enabled: boolean;
};

export type ProviderPatch = Partial<{
  base_url: string;
  auth_style: AuthStyle;
  api_key: string;
  enabled: boolean;
}>;

export type AiModel = {
  id: number;
  provider_id: number;
  model_id: string;
  label: string;
  input_price: string | null;
  output_price: string | null;
  strengths: string;
  enabled: boolean;
};

export type ModelPatch = Partial<{
  label: string;
  input_price: string | null;
  output_price: string | null;
  strengths: string;
  enabled: boolean;
}>;

export type Purpose = {
  id: number;
  key: string;
  title: string;
  description: string;
  primary_model_id: number | null;
  fallback_model_id: number | null;
  enabled: boolean;
};

export type PurposePatch = Partial<{
  title: string;
  description: string;
  primary_model_id: number | null;
  fallback_model_id: number | null;
  enabled: boolean;
}>;

export type Recommendation = {
  purpose_key: string;
  provider: string;
  model_id: string;
  rationale: string;
};

export function listProviders() {
  return api<Provider[]>("/ai/providers");
}
export function createProvider(body: ProviderCreate) {
  return api<Provider>("/ai/providers", { method: "POST", body: JSON.stringify(body) });
}
export function updateProvider(id: number, patch: ProviderPatch) {
  return api<Provider>(`/ai/providers/${id}`, { method: "PUT", body: JSON.stringify(patch) });
}
export function deleteProvider(id: number) {
  return api<void>(`/ai/providers/${id}`, { method: "DELETE" });
}
export function refreshModels(providerId: number) {
  return api<{ imported: number; updated: number }>(
    `/ai/providers/${providerId}/models/refresh`,
    { method: "POST" },
  );
}
export function listModels(providerId?: number) {
  const q = providerId != null ? `?provider_id=${providerId}` : "";
  return api<AiModel[]>(`/ai/models${q}`);
}
export function updateModel(id: number, patch: ModelPatch) {
  return api<AiModel>(`/ai/models/${id}`, { method: "PUT", body: JSON.stringify(patch) });
}
export function deleteModel(id: number) {
  return api<void>(`/ai/models/${id}`, { method: "DELETE" });
}
export function listPurposes() {
  return api<Purpose[]>("/ai/purposes");
}
export function updatePurpose(key: string, patch: PurposePatch) {
  return api<Purpose>(`/ai/purposes/${key}`, { method: "PUT", body: JSON.stringify(patch) });
}
export function recommend() {
  return api<Recommendation[]>("/ai/router/recommend", { method: "POST" });
}
export function testPurpose(key: string) {
  return api<{ ok: boolean; detail: string }>(`/ai/purposes/${key}/test`, { method: "POST" });
}
