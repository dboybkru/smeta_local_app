import { api } from "./client";

export const getDadataSettings = () => api<{ has_token: boolean }>("/settings/dadata");
export const setDadataToken = (token: string) =>
  api<{ has_token: boolean }>("/settings/dadata", { method: "PUT", body: JSON.stringify({ token }) });
