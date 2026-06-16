import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { listOrgUsers, updateOrgUser } from "../api/orgs";
import type { OrgUser } from "../api/orgs";

export default function AdminUsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const orgId = user?.org_id ?? null;

  async function load() {
    if (orgId == null) return;
    try {
      setUsers(await listOrgUsers(orgId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId]);

  async function setStatus(id: number, status: "active" | "blocked") {
    if (orgId == null) return;
    setBusyId(id);
    setError("");
    try {
      await updateOrgUser(orgId, id, { status });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка изменения статуса");
    } finally {
      setBusyId(null);
    }
  }

  if (orgId == null) {
    return (
      <div className="p-8">
        <h1 className="mb-4 font-serif text-xl text-stone-900">Пользователи</h1>
        <p className="text-stone-500">Аккаунт не привязан к организации.</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="mb-4 font-serif text-xl text-stone-900">Пользователи</h1>
      {error && <p role="alert" className="text-red-600">{error}</p>}
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-stone-300 text-left text-stone-500">
            <th className="py-2">Email</th>
            <th>Имя</th>
            <th>Роль</th>
            <th>Статус</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className="border-b border-stone-200">
              <td className="py-2">{u.email}</td>
              <td>{u.name}</td>
              <td>{u.role}</td>
              <td>{u.status}</td>
              <td className="space-x-2 text-right">
                {u.status !== "active" && (
                  <button
                    onClick={() => void setStatus(u.id, "active")}
                    disabled={busyId === u.id}
                    className="rounded border border-green-700 px-2 py-1 text-green-700 disabled:opacity-50"
                  >
                    Одобрить
                  </button>
                )}
                {u.status !== "blocked" && (
                  <button
                    onClick={() => void setStatus(u.id, "blocked")}
                    disabled={busyId === u.id}
                    className="rounded border border-red-700 px-2 py-1 text-red-700 disabled:opacity-50"
                  >
                    Заблокировать
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
