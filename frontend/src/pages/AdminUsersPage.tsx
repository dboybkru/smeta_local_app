import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { User } from "../auth/AuthContext";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState("");

  async function load() {
    try {
      setUsers(await api<User[]>("/admin/users"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function setStatus(id: number, status: "active" | "blocked") {
    await api(`/admin/users/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status }),
    });
    await load();
  }

  return (
    <div className="p-8">
      <h1 className="mb-4 font-serif text-xl text-stone-900">Пользователи</h1>
      {error && <p className="text-red-600">{error}</p>}
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
                    className="rounded border border-green-700 px-2 py-1 text-green-700"
                  >
                    Одобрить
                  </button>
                )}
                {u.status !== "blocked" && (
                  <button
                    onClick={() => void setStatus(u.id, "blocked")}
                    className="rounded border border-red-700 px-2 py-1 text-red-700"
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
