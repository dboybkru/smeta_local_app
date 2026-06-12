import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function AppHeader() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin";
  return (
    <header className="flex items-center justify-between border-b border-stone-200 bg-white px-6 py-3">
      <Link to="/" className="font-serif text-lg text-stone-900">SmetaApp</Link>
      <nav className="flex items-center gap-4 text-sm">
        <Link to="/catalog" className="text-stone-600 hover:text-stone-900">Каталог</Link>
        {isAdmin && (
          <Link to="/import" className="text-stone-600 hover:text-stone-900">Импорт</Link>
        )}
        {isAdmin && (
          <Link to="/price-levels" className="text-stone-600 hover:text-stone-900">Уровни цен</Link>
        )}
        {isAdmin && (
          <Link to="/admin/users" className="text-stone-600 hover:text-stone-900">Пользователи</Link>
        )}
        <span className="text-stone-400">{user?.email}</span>
        <button onClick={logout} className="text-stone-600 hover:text-stone-900">Выйти</button>
      </nav>
    </header>
  );
}
