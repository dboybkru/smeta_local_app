import { useEffect, useState } from "react";
import AppHeader from "../components/AppHeader";
import { useAuth } from "../auth/AuthContext";
import {
  listOrgs,
  createOrg,
  listOrgUsers,
  inviteUser,
  updateOrgUser,
  type Org,
  type OrgUser,
  type OrgRole,
} from "../api/orgs";

const STATUS_LABELS: Record<string, string> = {
  active: "Активен",
  blocked: "Заблокирован",
  pending: "На рассмотрении",
  invited: "Приглашён",
};

export default function OrgsPage() {
  const { user } = useAuth();

  if (!user?.is_superuser) {
    return (
      <div className="min-h-screen bg-stone-50">
        <AppHeader />
        <main className="p-8">
          <p className="text-stone-500">Доступ запрещён.</p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <AppHeader />
      <main className="p-8">
        <h1 className="mb-6 font-serif text-xl text-stone-900">Организации</h1>
        <OrgsSection />
      </main>
    </div>
  );
}

function OrgsSection() {
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [error, setError] = useState("");
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [selectedOrg, setSelectedOrg] = useState<Org | null>(null);

  async function load() {
    try {
      setOrgs(await listOrgs());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    setError("");
    try {
      await createOrg(newName.trim());
      setNewName("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка создания");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex gap-8">
      {/* Left panel: org list + create */}
      <section className="w-72 shrink-0">
        <h2 className="mb-3 font-serif text-lg text-stone-900">Список организаций</h2>
        {error && (
          <p role="alert" className="mb-2 text-sm text-red-600">
            {error}
          </p>
        )}
        <ul className="mb-4 divide-y divide-stone-200 rounded border border-stone-200 bg-white">
          {orgs.length === 0 && (
            <li className="px-3 py-2 text-sm text-stone-400">Нет организаций</li>
          )}
          {orgs.map((org) => (
            <li key={org.id}>
              <button
                onClick={() => setSelectedOrg(org)}
                className={`w-full px-3 py-2 text-left text-sm hover:bg-stone-50 ${
                  selectedOrg?.id === org.id ? "bg-stone-100 font-medium" : ""
                }`}
              >
                <span className="block text-stone-900">{org.name}</span>
                <span className="text-xs text-stone-400">{org.user_count} польз.</span>
              </button>
            </li>
          ))}
        </ul>

        <div className="flex gap-2">
          <input
            type="text"
            aria-label="Название новой организации"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void handleCreate()}
            placeholder="Название"
            className="min-w-0 flex-1 rounded border border-stone-300 px-2 py-1 text-sm"
          />
          <button
            onClick={() => void handleCreate()}
            disabled={creating || !newName.trim()}
            className="rounded border border-stone-700 px-3 py-1 text-sm text-stone-700 disabled:opacity-50"
          >
            Создать
          </button>
        </div>
      </section>

      {/* Right panel: org users */}
      {selectedOrg && (
        <OrgUsersPanel
          org={selectedOrg}
          onChanged={load}
        />
      )}
    </div>
  );
}

function OrgUsersPanel({ org, onChanged }: { org: Org; onChanged: () => void }) {
  const [users, setUsers] = useState<OrgUser[]>([]);
  const [error, setError] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<OrgRole>("estimator");
  const [inviting, setInviting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function load() {
    try {
      setUsers(await listOrgUsers(org.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки пользователей");
    }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    setUsers([]);
    setError("");
    void load();
  }, [org.id]);

  async function handleInvite() {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setError("");
    try {
      await inviteUser(org.id, { email: inviteEmail.trim(), role: inviteRole });
      setInviteEmail("");
      await load();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка приглашения");
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(uid: number, role: OrgRole) {
    setBusyId(uid);
    setError("");
    try {
      await updateOrgUser(org.id, uid, { role });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка изменения роли");
    } finally {
      setBusyId(null);
    }
  }

  async function handleStatusToggle(uid: number, currentStatus: string) {
    const newStatus = currentStatus === "blocked" ? "active" : "blocked";
    setBusyId(uid);
    setError("");
    try {
      await updateOrgUser(org.id, uid, { status: newStatus as "active" | "blocked" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка изменения статуса");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="flex-1">
      <h2 className="mb-3 font-serif text-lg text-stone-900">
        Пользователи · {org.name}
      </h2>

      {error && (
        <p role="alert" className="mb-2 text-sm text-red-600">
          {error}
        </p>
      )}

      {/* Invite form */}
      <div className="mb-4 flex flex-wrap items-end gap-2">
        <input
          type="email"
          aria-label="Email для приглашения"
          value={inviteEmail}
          onChange={(e) => setInviteEmail(e.target.value)}
          placeholder="Email"
          className="rounded border border-stone-300 px-2 py-1 text-sm"
        />
        <select
          aria-label="Роль приглашаемого"
          value={inviteRole}
          onChange={(e) => setInviteRole(e.target.value as OrgRole)}
          className="rounded border border-stone-300 px-2 py-1 text-sm"
        >
          <option value="org_admin">Администратор</option>
          <option value="estimator">Сметчик</option>
          <option value="viewer">Наблюдатель</option>
        </select>
        <button
          onClick={() => void handleInvite()}
          disabled={inviting || !inviteEmail.trim()}
          className="rounded border border-stone-700 px-3 py-1 text-sm text-stone-700 disabled:opacity-50"
        >
          Пригласить
        </button>
      </div>

      {/* Users table */}
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
          {users.length === 0 && (
            <tr>
              <td colSpan={5} className="py-3 text-stone-400">
                Пользователей нет
              </td>
            </tr>
          )}
          {users.map((u) => (
            <tr key={u.id} className="border-b border-stone-200">
              <td className="py-2">{u.email}</td>
              <td>{u.name}</td>
              <td>
                <select
                  aria-label={`Роль ${u.email}`}
                  value={u.role}
                  disabled={busyId === u.id}
                  onChange={(e) => void handleRoleChange(u.id, e.target.value as OrgRole)}
                  className="rounded border border-stone-200 px-1 py-0.5 text-xs disabled:opacity-50"
                >
                  <option value="org_admin">Администратор</option>
                  <option value="estimator">Сметчик</option>
                  <option value="viewer">Наблюдатель</option>
                </select>
              </td>
              <td>
                <span
                  className={
                    u.status === "active"
                      ? "text-green-700"
                      : u.status === "blocked"
                      ? "text-red-600"
                      : "text-stone-400"
                  }
                >
                  {STATUS_LABELS[u.status] ?? u.status}
                </span>
              </td>
              <td className="space-x-2 text-right">
                {u.status !== "blocked" && (
                  <button
                    onClick={() => void handleStatusToggle(u.id, u.status)}
                    disabled={busyId === u.id}
                    className="rounded border border-red-700 px-2 py-1 text-xs text-red-700 disabled:opacity-50"
                  >
                    Заблокировать
                  </button>
                )}
                {u.status === "blocked" && (
                  <button
                    onClick={() => void handleStatusToggle(u.id, u.status)}
                    disabled={busyId === u.id}
                    className="rounded border border-green-700 px-2 py-1 text-xs text-green-700 disabled:opacity-50"
                  >
                    Активировать
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
