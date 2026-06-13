import { api } from "./client";

export type PublicLink = {
  id: number;
  estimate_id: number;
  token: string;
  level: string;
  expires_at: string | null;
  watermark_enabled: boolean;
  watermark_text: string;
  revoked: boolean;
  created_at: string;
};

export type PublicLinkCreate = {
  level: string;
  expires_at?: string | null;
  watermark_enabled?: boolean;
  watermark_text?: string;
};

const j = (b: unknown) => JSON.stringify(b);

export const listLinks = (estimateId: number) =>
  api<PublicLink[]>(`/estimates/${estimateId}/public-links`);
export const createLink = (estimateId: number, body: PublicLinkCreate) =>
  api<PublicLink>(`/estimates/${estimateId}/public-links`, { method: "POST", body: j(body) });
export const revokeLink = (linkId: number) =>
  api<void>(`/public-links/${linkId}`, { method: "DELETE" });
