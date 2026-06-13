import { api } from "./client";

export type Contacts = { phone: string; email: string; address: string; site: string };

export type Profile = {
  id: number;
  org_name: string;
  inn: string;
  contacts: Contacts;
  bank_requisites: string;
  utp: string[];
  cases: string[];
  guarantee: string;
  logo_url: string;
  updated_at: string;
};

export type ProfileIn = Omit<Profile, "id" | "updated_at">;

const j = (b: unknown) => JSON.stringify(b);

export const getProfile = () => api<Profile>("/profile");
export const putProfile = (body: ProfileIn) => api<Profile>("/profile", { method: "PUT", body: j(body) });
