import { api } from "./client";
import type { EstimateDetail } from "./estimates";

export type ChatMessage = { role: "user" | "assistant"; content: string };

// Операции changeset — поле op дискриминатор; остальные поля зависят от op.
export type Operation = {
  op: string;
  name?: string;
  section_name?: string;
  catalog_item_id?: number;
  qty?: string;
  unit?: string;
  material_price?: string | null;
  work_price?: string | null;
  line_id?: number;
  section_id?: number;
  markup_percent?: string;
  vat_enabled?: boolean;
  vat_rate?: string | null;
};

export type ChatResponse = { reply: string; operations: Operation[] };

export function getAssistantHistory(estimateId: number) {
  return api<ChatMessage[]>(`/estimates/${estimateId}/assistant/messages`);
}

export function chatAssistant(estimateId: number, message: string) {
  return api<ChatResponse>(`/estimates/${estimateId}/assistant/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function applyChangeset(estimateId: number, operations: Operation[]) {
  return api<EstimateDetail>(`/estimates/${estimateId}/assistant/apply`, {
    method: "POST",
    body: JSON.stringify({ operations }),
  });
}
