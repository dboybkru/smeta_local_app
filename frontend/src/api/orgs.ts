import { api } from "./client";

export type Org = {
  id: number;
  name: string;
  user_count: number;
};

export type OrgUser = {
  id: number;
  email: string;
  name: string;
  role: string;
  status: string;
};

export type InviteResult = {
  id: number;
  email: string;
  role: string;
  status: string;
  email_sent: boolean;
  invite_link: string;
};

export type InviteInfo = {
  email: string;
  org_name: string;
  role: string;
};

export type OrgRole = "org_admin" | "estimator" | "viewer";
export type OrgUserStatus = "active" | "blocked" | "pending" | "invited";

export function listOrgs(): Promise<Org[]> {
  return api<Org[]>("/orgs");
}

export function createOrg(name: string): Promise<Org> {
  return api<Org>("/orgs", { method: "POST", body: JSON.stringify({ name }) });
}

export function renameOrg(id: number, name: string): Promise<Org> {
  return api<Org>(`/orgs/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
}

export function listOrgUsers(orgId: number): Promise<OrgUser[]> {
  return api<OrgUser[]>(`/orgs/${orgId}/users`);
}

export function inviteUser(
  orgId: number,
  body: { email: string; role: OrgRole },
): Promise<InviteResult> {
  return api<InviteResult>(`/orgs/${orgId}/users`, { method: "POST", body: JSON.stringify(body) });
}

export function resendInvite(orgId: number, uid: number): Promise<InviteResult> {
  return api<InviteResult>(`/orgs/${orgId}/users/${uid}/resend-invite`, { method: "POST" });
}

export function getInvite(token: string): Promise<InviteInfo> {
  return api<InviteInfo>(`/auth/invite/${token}`);
}

export function acceptInvite(
  token: string,
  body: { name: string; password: string },
): Promise<unknown> {
  return api<unknown>(`/auth/invite/${token}/accept`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateOrgUser(
  orgId: number,
  uid: number,
  patch: { role?: OrgRole; status?: OrgUserStatus },
): Promise<OrgUser> {
  return api<OrgUser>(`/orgs/${orgId}/users/${uid}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}
