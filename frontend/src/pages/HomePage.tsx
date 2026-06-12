import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function HomePage() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-stone-50">
      <header className="flex items-center justify-between border-b border-stone-200 bg-white px-6 py-3">
        <span className="font-serif text-lg text-stone-900">SmetaApp</span>
        <nav className="flex items-center gap-4 text-sm">
          {user?.role === "admin" && (
            <Link to="/admin/users" className="text-stone-600 hover:text-stone-900">
              Пользователи
            </Link>
          )}
          <span className="text-stone-400">{user?.email}</span>
          <button onClick={logout} className="text-stone-600 hover:text-stone-900">
            Выйти
          </button>
        </nav>
      </header>
      <main className="p-8 text-stone-600">
        Каркас готов. Сметы и прайсы появятся в следующих фазах.
      </main>
    </div>
  );
}
