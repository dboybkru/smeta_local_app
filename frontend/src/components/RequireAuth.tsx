import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function RequireAuth() {
  const { user, logout } = useAuth();
  if (user === undefined) return <div className="p-8 text-stone-500">Загрузка…</div>;
  if (user === null) return <Navigate to="/login" replace />;
  if (user.status !== "active")
    return (
      <div className="flex min-h-screen items-center justify-center bg-stone-50">
        <div className="max-w-md rounded-lg border border-stone-200 bg-white p-8 text-center">
          <h1 className="mb-2 font-serif text-xl text-stone-900">Аккаунт на рассмотрении</h1>
          <p className="text-sm text-stone-600">
            Администратор должен одобрить ваш доступ. Загляните позже.
          </p>
          <button onClick={logout} className="mt-4 text-sm text-stone-500 underline">
            Выйти
          </button>
        </div>
      </div>
    );
  return <Outlet />;
}
