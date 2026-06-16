import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { getInvite, acceptInvite, type InviteInfo } from "../api/orgs";
import { ApiError } from "../api/client";

type PageState = "loading" | "ready" | "not_found" | "expired" | "done";

export default function InvitePage() {
  const { token } = useParams<{ token: string }>();
  const { reload } = useAuth();
  const navigate = useNavigate();

  const [state, setState] = useState<PageState>("loading");
  const [info, setInfo] = useState<InviteInfo | null>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) {
      setState("not_found");
      return;
    }
    getInvite(token)
      .then((data) => {
        setInfo(data);
        setState("ready");
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 410) {
          setState("expired");
        } else {
          setState("not_found");
        }
      });
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError("");
    setBusy(true);
    try {
      await acceptInvite(token, { name, password });
      await reload();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50">
      <div className="w-full max-w-sm space-y-6 rounded-lg border border-stone-200 bg-white p-8">
        <h1 className="font-serif text-2xl text-stone-900">SmetaApp</h1>

        {state === "loading" && (
          <p className="text-sm text-stone-500">Загрузка…</p>
        )}

        {state === "not_found" && (
          <p role="alert" className="text-sm text-red-600">
            Приглашение не найдено.
          </p>
        )}

        {state === "expired" && (
          <p role="alert" className="text-sm text-red-600">
            Срок приглашения истёк. Попросите администратора отправить новое.
          </p>
        )}

        {state === "ready" && info && (
          <>
            <p className="text-sm text-stone-600">
              Вас пригласили в{" "}
              <span className="font-medium text-stone-900">{info.org_name}</span>{" "}
              как{" "}
              <span className="font-medium text-stone-900">{info.role}</span>.
            </p>
            <p className="text-xs text-stone-400">{info.email}</p>

            <form onSubmit={submit} className="space-y-4">
              <div>
                <label htmlFor="invite-name" className="block text-sm text-stone-600">
                  Ваше имя
                </label>
                <input
                  id="invite-name"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full rounded border border-stone-300 px-3 py-2"
                />
              </div>
              <div>
                <label htmlFor="invite-password" className="block text-sm text-stone-600">
                  Пароль
                </label>
                <input
                  id="invite-password"
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 w-full rounded border border-stone-300 px-3 py-2"
                />
              </div>
              {error && (
                <p role="alert" className="text-sm text-red-600">
                  {error}
                </p>
              )}
              <button
                type="submit"
                disabled={busy}
                className="w-full rounded border border-stone-900 px-4 py-2 text-stone-900 disabled:opacity-50"
              >
                Создать аккаунт и войти
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
