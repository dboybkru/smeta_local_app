import { afterEach, describe, expect, it, vi } from "vitest";
import {
  listOrgs,
  createOrg,
  renameOrg,
  listOrgUsers,
  inviteUser,
  updateOrgUser,
} from "./orgs";

function mockFetchOnce(data: unknown, status = 200) {
  return vi.fn(async () =>
    new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" },
    })
  );
}

afterEach(() => vi.restoreAllMocks());

describe("orgs api", () => {
  it("listOrgs GETs /api/orgs", async () => {
    const fetchMock = mockFetchOnce([{ id: 1, name: "Акме", user_count: 3 }]);
    vi.stubGlobal("fetch", fetchMock);
    const orgs = await listOrgs();
    expect(orgs[0].name).toBe("Акме");
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/orgs");
  });

  it("createOrg POSTs to /api/orgs with name", async () => {
    const fetchMock = mockFetchOnce({ id: 2, name: "Новая", user_count: 0 });
    vi.stubGlobal("fetch", fetchMock);
    const org = await createOrg("Новая");
    expect(org.id).toBe(2);
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/orgs");
    expect((calls[0][1] as RequestInit).method).toBe("POST");
    expect(JSON.parse((calls[0][1] as RequestInit).body as string)).toEqual({ name: "Новая" });
  });

  it("renameOrg PATCHes /api/orgs/{id}", async () => {
    const fetchMock = mockFetchOnce({ id: 1, name: "Переименована", user_count: 3 });
    vi.stubGlobal("fetch", fetchMock);
    await renameOrg(1, "Переименована");
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/orgs/1");
    expect((calls[0][1] as RequestInit).method).toBe("PATCH");
  });

  it("listOrgUsers GETs /api/orgs/{id}/users", async () => {
    const fetchMock = mockFetchOnce([
      { id: 5, email: "u@u.ru", name: "Юзер", role: "estimator", status: "active" },
    ]);
    vi.stubGlobal("fetch", fetchMock);
    const users = await listOrgUsers(1);
    expect(users[0].email).toBe("u@u.ru");
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/orgs/1/users");
  });

  it("inviteUser POSTs to /api/orgs/{id}/users", async () => {
    const fetchMock = mockFetchOnce({
      id: 7,
      email: "new@u.ru",
      name: "",
      role: "estimator",
      status: "invited",
    });
    vi.stubGlobal("fetch", fetchMock);
    await inviteUser(1, { email: "new@u.ru", role: "estimator" });
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/orgs/1/users");
    expect((calls[0][1] as RequestInit).method).toBe("POST");
    expect(JSON.parse((calls[0][1] as RequestInit).body as string)).toEqual({
      email: "new@u.ru",
      role: "estimator",
    });
  });

  it("updateOrgUser PATCHes /api/orgs/{orgId}/users/{uid}", async () => {
    const fetchMock = mockFetchOnce({
      id: 5,
      email: "u@u.ru",
      name: "Юзер",
      role: "viewer",
      status: "active",
    });
    vi.stubGlobal("fetch", fetchMock);
    await updateOrgUser(1, 5, { role: "viewer" });
    const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0][0]).toBe("/api/orgs/1/users/5");
    expect((calls[0][1] as RequestInit).method).toBe("PATCH");
    expect(JSON.parse((calls[0][1] as RequestInit).body as string)).toEqual({ role: "viewer" });
  });
});
