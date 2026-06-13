import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function AppHeader() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin";
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-stone-200 bg-white px-6 py-3">
      <Link to="/" className="shrink-0 font-serif text-lg text-stone-900">SmetaApp</Link>
      <nav className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <Link to="/catalog" className="text-stone-600 hover:text-stone-900">Каталог</Link>
        <Link to="/estimates" className="text-stone-600 hover:text-stone-900">Сметы</Link>
        <Link to="/profile" className="text-stone-600 hover:text-stone-900">Реквизиты</Link>
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
