import { api } from "./client";

export type DadataStatus = { has_token: boolean; has_secret: boolean };

export const getDadataSettings = () => api<DadataStatus>("/settings/dadata");
export const saveDadata = (token: string, secret: string) =>
  api<DadataStatus>("/settings/dadata", { method: "PUT", body: JSON.stringify({ token, secret }) });

export type YandexStatus = { client_id: string; has_secret: boolean };

export const getYandex = () => api<YandexStatus>("/settings/yandex");
export const setYandex = (body: { client_id?: string; secret?: string }) =>
  api<YandexStatus>("/settings/yandex", { method: "PUT", body: JSON.stringify(body) });

export type AuthConfig = { yandex_enabled: boolean };

/** Fetches auth feature flags from the backend. Never throws — returns defaults on error. */
export async function getAuthConfig(): Promise<AuthConfig> {
  try {
    return await api<AuthConfig>("/auth/config");
  } catch {
    return { yandex_enabled: false };
  }
}
