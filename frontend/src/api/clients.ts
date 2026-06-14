import { api } from "./client";

export type Client = {
  id: number;
  name: string;
  default_price_level_id: number | null;
  inn: string | null; kpp: string | null; ogrn: string | null; type: string | null;
  address: string | null; actual_address: string | null;
  phone: string | null; email: string | null; contact_person: string | null;
  bank_name: string | null; bank_account: string | null; bik: string | null;
};

export type ClientInput = Partial<Omit<Client, "id">> & { name: string };
export type Suggestion = {
  value: string; inn: string; kpp: string; ogrn: string;
  name_short: string; address: string; management: string; type: string; status: string;
};

export const listClients = () => api<Client[]>("/clients");
export const getClient = (id: number) => api<Client>(`/clients/${id}`);
export const createClient = (body: ClientInput) =>
  api<Client>("/clients", { method: "POST", body: JSON.stringify(body) });
export const updateClient = (id: number, patch: Partial<ClientInput>) =>
  api<Client>(`/clients/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
export const suggestParties = (q: string) =>
  api<Suggestion[]>(`/clients/suggest?q=${encodeURIComponent(q)}`);
