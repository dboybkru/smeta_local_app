import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { getAuthConfig } from "../api/settings";

export default function LoginPage() {
  const { loginWithPassword } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [yandexEnabled, setYandexEnabled] = useState(false);

  useEffect(() => {
    getAuthConfig().then((cfg) => setYandexEnabled(cfg.yandex_enabled));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await loginWithPassword(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50">
      <div className="w-full max-w-sm space-y-6 rounded-lg border border-stone-200 bg-white p-8">
        <h1 className="font-serif text-2xl text-stone-900">SmetaApp</h1>
        {yandexEnabled && (
          <>
            <a
              href="/api/auth/yandex/login"
              className="block w-full rounded bg-stone-900 px-4 py-2 text-center text-white"
            >
              Войти с Яндексом
            </a>
            <div className="text-center text-sm text-stone-400">или по email</div>
          </>
        )}
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm text-stone-600">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded border border-stone-300 px-3 py-2"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm text-stone-600">
              Пароль
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded border border-stone-300 px-3 py-2"
            />
          </div>
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded border border-stone-900 px-4 py-2 text-stone-900 disabled:opacity-50"
          >
            Войти
          </button>
        </form>
      </div>
    </div>
  );
}
