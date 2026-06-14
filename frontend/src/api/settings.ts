import { api } from "./client";

export type DadataStatus = { has_token: boolean; has_secret: boolean };

export const getDadataSettings = () => api<DadataStatus>("/settings/dadata");
export const saveDadata = (token: string, secret: string) =>
  api<DadataStatus>("/settings/dadata", { method: "PUT", body: JSON.stringify({ token, secret }) });
